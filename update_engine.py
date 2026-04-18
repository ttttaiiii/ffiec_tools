import os
import time
import glob
import zipfile
import shutil
import json
import re
import pandas as pd
import datetime
import xml.etree.ElementTree as ET
from google.cloud import bigquery
import streamlit as st

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# System chromedriver — version-matched to Streamlit Cloud's Chromium install
CHROMEDRIVER_PATH = "/usr/bin/chromedriver"
FFIEC_BULK_URL = "https://cdr.ffiec.gov/public/pws/downloadbulkdata.aspx"

# --- Configuration Constants ---
TABLE_FINANCIALS = "call_reports_financials"
TABLE_LOG = "migration_log"

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # In Streamlit Cloud, the driver is located at this path after adding it to packages.txt
    service = Service("/usr/bin/chromedriver")
    
    return webdriver.Chrome(service=service, options=chrome_options)

def wipe_period(report_date, client, project_id, dataset):
    """Deletes data for a specific period from BigQuery to allow for a clean re-run."""
    queries = [
        f"DELETE FROM `{project_id}.{dataset}.{TABLE_FINANCIALS}` WHERE report_date = '{report_date}'",
        f"DELETE FROM `{project_id}.{dataset}.{TABLE_LOG}` WHERE report_date = '{report_date}'"
    ]
    for q in queries:
        client.query(q).result()

def get_date_objects(date_str):
    """Helper for range filtering logic."""
    try:
        return datetime.strptime(date_str, "%m/%d/%Y")
    except:
        return None

def process_xml_worker_by_content(xml_content, report_date):
    """
    Core parsing logic (Kept same as original).
    Parses XML content and extracts financial MDRM values.
    """
    rows = []
    try:
        root = ET.fromstring(xml_content)
        # Extract IDRSSD (Bank Identifier)
        idrssd = None
        for entity in root.findall(".//{http://www.xbrl.org/2003/instance}identifier"):
            idrssd = entity.text
            break
        
        # Extract all financial facts (MDRM codes)
        for element in root:
            # Common FFIEC namespaces
            if 'cc:' in element.tag or 'inst:' in element.tag:
                tag_name = element.tag.split('}')[-1]
                value = element.text
                unit_ref = element.attrib.get('unitRef')
                context_ref = element.attrib.get('contextRef')
                
                if value and value.strip():
                    rows.append({
                        'idrssd': idrssd,
                        'report_date': report_date,
                        'concept_reference': tag_name,
                        'value': value,
                        'unit_ref': unit_ref,
                        'context_ref': context_ref
                    })
    except Exception:
        pass
    return rows

def run_bulk_download(download_dir, mode="new", start_date_str=None, end_date_str=None):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")           # modern headless flag for Chrome 112+
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    )

    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=chrome_options)
    # Mask webdriver flag so ASP.NET sites do not detect and block headless Chrome
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
    )

    wait = WebDriverWait(driver, 45)  # generous timeout for Streamlit Cloud + FFIEC server

    try:
        yield ("Navigating to FFIEC download page...", 0.05)
        driver.get(FFIEC_BULK_URL)

        # Wait for full page load (ASP.NET pages can be slow)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

        # Find the report dropdown — surface a diagnostic error if missing
        try:
            report_dropdown = wait.until(
                EC.element_to_be_clickable((By.ID, "ReportTypeDropDownList"))
            )
        except Exception:
            raise RuntimeError(
                f"Could not find ReportTypeDropDownList after 45s. "
                f"Page title: '{driver.title}'. "
                f"Source snippet: {driver.page_source[:1500]}"
            )

        Select(report_dropdown).select_by_visible_text(
            "Call Reports -- Balance Sheet, Income Statement, Past Due -- Four Periods"
        )

        # ASP.NET postback — wait a bit then confirm dates dropdown is ready
        time.sleep(3)
        date_dropdown_el = wait.until(
            EC.element_to_be_clickable((By.ID, "DatesDropDownList"))
        )

        all_options = [
            opt.text.strip()
            for opt in Select(date_dropdown_el).options
            if opt.text.strip()
        ]

        if not all_options:
            raise RuntimeError("DatesDropDownList loaded but contained no date options.")

        target_dates = []
        if mode == "range":
            start_dt = get_date_objects(start_date_str)
            end_dt = get_date_objects(end_date_str)
            target_dates = [
                opt for opt in all_options
                if get_date_objects(opt) and (start_dt <= get_date_objects(opt) <= end_dt)
            ]
        else:
            target_dates = all_options

        if not target_dates:
            yield ("No new data to download.", 1.0)
            return

        for idx, target in enumerate(target_dates):
            current_progress = (idx / len(target_dates)) * 0.9 + 0.1
            yield (f"Downloading {target}...", current_progress)

            Select(driver.find_element(By.ID, "DatesDropDownList")).select_by_visible_text(target)
            time.sleep(1)
            driver.execute_script(
                "arguments[0].click();",
                driver.find_element(By.ID, "Download_0")
            )

            # Wait up to 2 minutes per file for download to finish
            time.sleep(5)
            for _ in range(60):
                if not glob.glob(os.path.join(download_dir, "*.crdownload")):
                    break
                time.sleep(2)

        yield ("Download complete.", 1.0)
    finally:
        driver.quit()

def run_bulk_parse(download_dir, client, project_id, dataset):
    """
    Parses ZIPs and uses BigQuery Load Jobs for high-performance ingestion.
    Replaces row-by-row SQL with Pandas-based Batch Loading.
    """
    zip_files = sorted(glob.glob(os.path.join(download_dir, "*.zip")))