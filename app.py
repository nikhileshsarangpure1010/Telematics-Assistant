import sys
import os
import argparse
import re
from typing import List, Dict, Tuple

# Configuration: Expected Payloads

EXPECTED_PAYLOADS = {
    "INAD": [
        {
            "name": "Connected to BMW Private Network (VLAN 77)",
            "positive": "vlanid [77], connectionClass [B2B] updated connection state from [CONNECTING] to [CONNECTED]",
            "negative": "[77], connectionClass [B2B] updated connection state from [DISCONNECTED] to [DISCONNECTED]",
            "solution": "Check the Certificates either it is empty or Corrupted, Please push it again. OR Enable the Mobile_Network_Activation JOB from ICON prj in Sterun."
        },
        {
            "name": "Connected to BMW Public Network (VLAN 107)",
            "positive": "vlanid [107], connectionClass [B2B] updated connection state from [CONNECTING] to [CONNECTED]",
            "negative": "[107], connectionClass [B2B] updated connection state from [DISCONNECTED] to [DISCONNECTED]",
            "solution": "Check the Certificates either it is empty or Corrupted, Please push it again."
        }
    ],
    "IBAM": [
        {
            "name": "OCSP Certificate Verified",
            "positive": "OCSP SSL certificate status: good",
            "negative": "OCSP SSL certificate status: revoked",
            "solution": "Certificate has been revoked or expired. Renew the certificate "
        },
        {
            "name": "Network Information Received",
            "positive": "Received network information about 1 active mobile connection",
            "negative": "Failed to retrieve network information",
            "solution": "Network Information not recieved, please check the you have the proper TMS Account."
        },
        {
            "name": "Communication Established between server and Client",
            "positive": "TLS handshake, Finished",
            "negative": "TLS handshake, Failed",
            "solution": "Delete the older certifcates and push it again."
        },
        {
            "name": "MCP Gateway Connected",
            "positive": "Connect to MCP gateway successfully",
            "negative": "Connecting to the MCP gateway failed",
            "solution": "Check MAC/IP sec and Certificate status."
        }
    ],
    "IDCEVO": [
        {
            "name": "IPsec and MACsec statuss are synced",
            "positive": "VSIP: ON_AVAILABLE",
            "negative": "VSIP: ON_UNAVAILABLE",
            "solution": "Check IP/SEC and MACSEC Status, it should be synced."
        },
        {
            "name": "EMEA Connection Established",
            "positive": "EMEA_E2E: ConnAck: Session present: true",
            "negative": "EMEA_E2E: Connect attempt (#0) was not successful",
            "solution": "Delete the Existence Certificates and Push it Again."
        }
    ],
    "WAVE": [

        {
            "name": "IPSec Connection between WAVE and MGU Established",
            "positive": "established between 160.48.199.98",
            "negative": "160.48.199.98 lost",
            "solution": "1.IP sec status should be same for all ECU's which can be changed via Tool32-->sterun routine-Ipsec status on/off.\n"
                        "2.Ensure after executing the job what is the response which we are getting possibility is also there that IP sec has been blocked for that ECU."
        },
        {
            "name": "Connection to MQTT Broker Established",
            "positive": "AbstractJoynrMessagingConnector REQUEST returns successful",
            "negative": "AbstractJoynrMessagingConnector REQUEST returns unsuccessful",
            "solution": "1. Time setting not proper, set time using prg according to the product.\n"
                        "2. Check time in IDC23 via winscp with Date command.\n"
                        "3. IF there is an issue with time in IDC23 set time only for IDC23 via command date -s \"2022-05-17 12:15:40\".\n"
                        "4. Do IDC23 reset and after setting time then give a lifecycle."
        }
    ],
        "IDC": [
        {
            "name": "OCSP Certificate Verified",
            "positive": "OCSP: SSL certificate status: good",
            "negative": "OCSP response has expired",
            "solution": "Check IDC service status and certificate provisioning."
        },
        {
            "name": "Mosquitto Connection established",
            "positive": "MosquittoConnection [BMW_MUC] Mosquitto Connection established",
            "negative": "Could not resolve host mqtt.e2e.cd-emea.bmw",
            "solution": "1. Time setting not proper, set time using prg according to the product.\n"
                        "2. Check time in IDC23 via winscp with Date command.\n"
                        "3. IF there is an issue with time in IDC23 set time only for IDC23 via command date -s \"2022-05-17 12:15:40\".\n"
                        "4. Do IDC23 reset and after setting time then give a lifecycle."
        },
        {
            "name": "IPSec Connection established",
            "positive": "160.48.199.98 established",
            "negative": "160.48.199.98 lost",
            "solution": "Enable IPSec status from Esys"
        },
        {
            "name": "TLS certificates",
            "positive": "Successfully initialized TLS certificate and key",
            "negative": "TLS certificates are incorrectly specified or inaccessible",
            "solution": "1. Check certificate binding status via e-sys.\n"
                        "2. Delete the existing certificates and push them again."
        }
    ]
}

# Configuration: File Paths (Optional: hardcode paths here if you don't want to use command line args)
FILE_PATHS = {
    "INAD": r"D:\Python\INAD.dlt",
    "IBAM": r"D:\Python\IBAM.dlt",
    "IDCEVO": r"D:\Python\IDCEVO.dlt",
    "IDC": r"D:\Python\IDC.dlt",
    "WAVE": r"D:\Python\WAVE.dlt"
}

def extract_vin_from_content(content: bytes) -> str:
    matches_vin = re.findall(b"Got VIN '([^']+)'", content)
    if matches_vin:
        return matches_vin[-1].decode('utf-8', errors='ignore')
    matches_vin = re.findall(b"VIN[^\n\-]*-\s*([A-Z0-9]{17})", content)
    if matches_vin:
        return matches_vin[-1].decode('utf-8', errors='ignore')
    matches_vin = re.findall(b"\[VIN[^\]]*\][^\n\-]*-\s*([A-Z0-9]{17})", content)
    if matches_vin:
        return matches_vin[-1].decode('utf-8', errors='ignore')
    return None

def extract_signal_data(content: bytes) -> Tuple[str, List[Dict[str, str]]]:
    sig_level = None
    cell_info_list = []

    # --- Signal Level ---
    m_sig = re.findall(b'SignalLevel:\s*([A-Za-z]+)', content)
    if not m_sig:
        m_sig = re.findall(b'Level\[(?:SIGNAL_STRENGTH_)?([A-Za-z_]+)\]', content, re.IGNORECASE)
    if m_sig:
        sig_level = m_sig[-1].decode('utf-8', errors='ignore').replace('SIGNAL_STRENGTH_', '')

    # --- Cell Signal Data: process line-by-line (same approach as IDCEVO/INAD) ---
    for line in content.split(b'\n'):

        # Pattern 1: IDCEVO/INAD format
        # snr [...], rssi [...], rsrp [...], rsrq [...]
        m = re.findall(
            b'snr\s+\[([-0-9]+)\],\s*rssi\s+\[([-0-9]+)\],\s*rsrp\s+\[([-0-9]+)\],\s*rsrq\s+\[([-0-9]+)\]',
            line
        )
        if m:
            for match in m:
                cell_info_list.append({
                    "RSSI": match[1].decode('utf-8', errors='ignore'),
                    "RSRP": match[2].decode('utf-8', errors='ignore'),
                    "RSRQ": match[3].decode('utf-8', errors='ignore')
                })
            continue # Skip pattern 2 for this line

        # Pattern 2: WAVE/IDC format, for example:
        # Lte Rsrp[92] Lte Rsrq[16] Lte Rssi[61]
        rsrp_m = re.findall(b'Lte\s+Rsrp\[(-?[0-9]+)\]', line, re.IGNORECASE)
        rsrq_m = re.findall(b'Lte\s+Rsrq\[(-?[0-9]+)\]', line, re.IGNORECASE)
        rssi_m = re.findall(b'Lte\s+Rssi\[(-?[0-9]+)\]', line, re.IGNORECASE)
        if rsrp_m and rsrq_m and rssi_m:
            rsrp_val = rsrp_m[0].decode('utf-8', errors='ignore')
            rsrq_val = rsrq_m[0].decode('utf-8', errors='ignore')
            rssi_val = rssi_m[0].decode('utf-8', errors='ignore')
            cell_info_list.append({
                "RSRP": f"-{rsrp_val}" if not rsrp_val.startswith('-') else rsrp_val,
                "RSRQ": f"-{rsrq_val}" if not rsrq_val.startswith('-') else rsrq_val,
                "RSSI": f"-{rssi_val}" if not rssi_val.startswith('-') else rssi_val
            })
            continue # Skip pattern 3 for this line

        # Pattern 3: IDC23 format, for example:
        # LTE signalStrength 26, rsrp 92, rsrq 16, rsnnr 14, w_ecio -1, lte_rssi 61
        m3 = re.findall(
            b'rsrp\s+(-?[0-9]+),\s*rsrq\s+(-?[0-9]+),.*?lte_rssi\s+(-?[0-9]+)',
            line, re.IGNORECASE
        )
        if m3:
            for match in m3:
                rsrp_val = match[0].decode('utf-8', errors='ignore')
                rsrq_val = match[1].decode('utf-8', errors='ignore')
                rssi_val = match[2].decode('utf-8', errors='ignore')
                cell_info_list.append({
                    "RSRP": f"-{rsrp_val}" if not rsrp_val.startswith('-') else rsrp_val,
                    "RSRQ": f"-{rsrq_val}" if not rsrq_val.startswith('-') else rsrq_val,
                    "RSSI": f"-{rssi_val}" if not rssi_val.startswith('-') else rssi_val
                })
            continue # Skip pattern 4 for this line

        # Pattern 4: qcril_qmi_cell_info_v12 format, for example:
        # Serving cell rsrp: -915. rsrq: -140. rssi: -607. srxlev: 0.
        m4 = re.findall(
            b'Serving\s+cell\s+rsrp:\s*(-?[0-9]+)\.\s*rsrq:\s*(-?[0-9]+)\.\s*rssi:\s*(-?[0-9]+)\.',
            line, re.IGNORECASE
        )
        if m4:
            for match in m4:
                # values are reported in tenths of a dB, e.g. -915 => -91.5
                cell_info_list.append({
                    "RSRP": str(int(match[0]) / 10),
                    "RSRQ": str(int(match[1]) / 10),
                    "RSSI": str(int(match[2]) / 10)
                })

    return sig_level, cell_info_list

def analyze_file(file_path: str, component_name: str) -> Tuple[Dict[str, any], Dict[str, str]]:
    """
    Checks for all expected payloads for a given component in a file.
    
    Args:
        file_path (str): Path to the .dlt file.
        component_name (str): Component name.
        
    Returns:
        Tuple[Dict[str, any], Dict[str, str]]: A dictionary mapping payload results and extracted values.
    """
    results = {}
    extracted = {}
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return {}, {}

    expected = EXPECTED_PAYLOADS.get(component_name, [])
    
    try:
        with open(file_path, 'rb') as f:
            content = f.read()

            # ECUID Verification
            ecu_id_map = {
                "INAD": b"INAD",
                "IBAM": b"IBAM",
                "IDCEVO": b"IDCE",
                "IDC": b"DC",
                "WAVE": b"WAV"
            }
            expected_ecu = ecu_id_map.get(component_name)
            if expected_ecu and expected_ecu not in content:
                print(f"\n--> ERROR: File '{file_path}' does NOT appear to be a valid {component_name} DLT file. (Expected ECUID '{expected_ecu.decode()}')")
                return {"Valid ECUID": False}, extracted
            
            for item in expected:
                if isinstance(item, str):
                    target_bytes = item.encode('utf-8')
                    results[item] = {"positive_found": target_bytes in content, "name": item}
                else:
                    pos_bytes = item["positive"].encode('utf-8')
                    neg_bytes = item.get("negative", "").encode('utf-8')
                    
                    pos_found = pos_bytes in content
                    neg_found = neg_bytes in content if item.get("negative") else False
                    
                    results[item["positive"]] = {
                        "name": item["name"],
                        "positive_found": pos_found,
                        "negative_found": neg_found,
                        "positive_payload": item["positive"],
                        "negative_payload": item.get("negative"),
                        "solution": item.get("solution")
                    }

            # Check general VIN & Signal extraction across all components
            vin_val = extract_vin_from_content(content)
            if vin_val:
                extracted["VIN"] = vin_val

            sig_level, cell_info = extract_signal_data(content)
            if sig_level:
                extracted["Signal Level"] = sig_level
            if cell_info:
                extracted["Cell_Info_DF"] = cell_info

            if component_name == "IDC":
                if re.search(rb"mqtts://mqtt\.e2e\.cd-emea\.bmw\b", content, re.IGNORECASE):
                    extracted["Environment"] = "INT"
                elif re.search(rb"mqtts://mqtt\.prod\.cd-emea\.bmw\b", content, re.IGNORECASE):
                    extracted["Environment"] = "PROD"
                else:
                    extracted["Environment"] = "Not Found"
            elif b"EMEA_PROD" in content:
                extracted["Environment"] = "PROD"
            elif b"EMEA_E2E" in content:
                extracted["Environment"] = "INT"
            else:
                extracted["Environment"] = "Not Found"

            if component_name == "IBAM":
                if "VIN" not in extracted:
                    extracted["VIN"] = "Not Found"

                # Extract BAM Version
                matches_bam = re.findall(b'NAME="icon-bam" VERSION="([^"]+)"', content)
                if matches_bam:
                    extracted["ICON Version"] = matches_bam[-1].decode('utf-8', errors='ignore')
                else:
                    extracted["ICON Version"] = "Not Found"

                matches_network = re.findall(b"NMCC:\s*'([^']+)',\s*NMNC:\s*'([^']+)',\s*SMCC:\s*'([^']+)',\s*SMNC:\s*'([^']+)'", content)
                if matches_network:
                    extracted["NMCC"] = matches_network[-1][0].decode('utf-8', errors='ignore')
                    extracted["NMNC"] = matches_network[-1][1].decode('utf-8', errors='ignore')
                    extracted["SMCC"] = matches_network[-1][2].decode('utf-8', errors='ignore')
                    extracted["SMNC"] = matches_network[-1][3].decode('utf-8', errors='ignore')
                else:
                    extracted["NMCC"] = "Not Found"
                    extracted["NMNC"] = "Not Found"
                    extracted["SMCC"] = "Not Found"
                    extracted["SMNC"] = "Not Found"
                    
                # Extract Provisioning Current State
                matches_status = re.findall(b'"dataStatus":"([^"]+)"', content)
                if matches_status:
                    extracted["Current State"] = matches_status[-1].decode('utf-8', errors='ignore')
                else:
                    extracted["Current State"] = "Not Found"

            elif component_name == "IDCEVO":
                # Extract IDCEVO Version
                matches_idcevo = re.findall(b'NAME="BMW IDCEVO" VERSION="([^"]+)"', content)
                if matches_idcevo:
                    extracted["IDCEVO Version"] = matches_idcevo[-1].decode('utf-8', errors='ignore')
                else:
                    extracted["IDCEVO Version"] = "Not Found"
                    
                # Extract Provisioning Current State
                matches_prov = re.findall(b"Setting provisioning data status to '([^']+)'", content)
                if matches_prov:
                    extracted["Current State"] = matches_prov[-1].decode('utf-8', errors='ignore')
                else:
                    extracted["Current State"] = "Not Found"

            elif component_name == "INAD":
                # Extract Network Provider / Carrier (e.g. JIO 4G) from PLMN pattern
                matches_plmn = re.findall(b'PLMN\{([^}]+)\}', content)
                network_provider = "Not Found"
                if matches_plmn:
                    for match in matches_plmn:
                        plmn_raw = match.decode('utf-8', errors='ignore')
                        parts = [p.strip() for p in plmn_raw.split(',')]
                        text_parts = [p for p in parts if p and p != '-' and not p.replace('-', '').isdigit()]
                        if text_parts:
                            network_provider = text_parts[0]
                extracted["Network Provider"] = network_provider

            elif component_name == "IDC":
                matches_idc = re.findall(b'(BMW IDC[0-9]*\s+[A-Za-z0-9]+-[A-Za-z0-9\.-]+?)(?=-nodex|_IDC|\s|$)', content, re.IGNORECASE)
                if not matches_idc:
                    matches_idc = re.findall(b'SW_VERSION[^\n\-]*-\s*([0-9A-Za-z\.\_\-]+)', content, re.IGNORECASE)
                if not matches_idc:
                    matches_idc = re.findall(b'NAME="BMW IDC[0-9]*" VERSION="([^"]+)"', content, re.IGNORECASE)
                if matches_idc:
                    extracted["IDC Version"] = matches_idc[-1].decode('utf-8', errors='ignore')
                else:
                    extracted["IDC Version"] = "Not Found"
                    
                normalized_content = content.replace(b"\x00", b"")
                matches_prov_source = re.findall(
                    rb"ProvSource[^A-Za-z0-9]+(JOYNR|LOCAL)\b",
                    normalized_content,
                    re.IGNORECASE
                )
                if matches_prov_source:
                    provisioning_source = matches_prov_source[-1].upper()
                    extracted["Current State"] = {
                        b"JOYNR": "OTA",
                        b"LOCAL": "DAS"
                    }[provisioning_source]
                else:
                    matches_prov = re.findall(b"Setting provisioning data status to '([^']+)'", content)
                    if matches_prov:
                        extracted["Current State"] = matches_prov[-1].decode('utf-8', errors='ignore')
                    else:
                        extracted["Current State"] = "Not Found"

                matches_vin = re.findall(b"Got VIN '([^']+)'", content)
                if matches_vin:
                    extracted["VIN"] = matches_vin[-1].decode('utf-8', errors='ignore')

                matches_network = re.findall(b"NMCC:\s*'([^']+)',\s*NMNC:\s*'([^']+)',\s*SMCC:\s*'([^']+)',\s*SMNC:\s*'([^']+)'", content)
                if matches_network:
                    extracted["NMCC"] = matches_network[-1][0].decode('utf-8', errors='ignore')
                    extracted["NMNC"] = matches_network[-1][1].decode('utf-8', errors='ignore')
                    extracted["SMCC"] = matches_network[-1][2].decode('utf-8', errors='ignore')
                    extracted["SMNC"] = matches_network[-1][3].decode('utf-8', errors='ignore')

                matches_plmn = re.findall(b'PLMN\{([^}]+)\}', content)
                if matches_plmn:
                    for match in matches_plmn:
                        plmn_raw = match.decode('utf-8', errors='ignore')
                        parts = [p.strip() for p in plmn_raw.split(',')]
                        text_parts = [p for p in parts if p and p != '-' and not p.replace('-', '').isdigit()]
                        if text_parts:
                            extracted["Network Provider"] = text_parts[0]


            elif component_name == "WAVE":
                matches_wave = re.findall(b'SW_VERSION[^\n\-]*-\s*([0-9A-Za-z\.\_\-]+)', content)
                if not matches_wave:
                    matches_wave = re.findall(b'NAME="BMW WAVE" VERSION="([^"]+)"', content)
                if matches_wave:
                    extracted["WAVE Version"] = matches_wave[-1].decode('utf-8', errors='ignore')
                else:
                    extracted["WAVE Version"] = "Not Found"

                matches_status = re.findall(b'"dataStatus":"([^"]+)"', content)
                if matches_status:
                    extracted["Current State"] = matches_status[-1].decode('utf-8', errors='ignore')
                else:
                    extracted["Current State"] = "Not Found"

                # NMCC (MCC) and NMNC (MNC) from "MCC 405, MNC 874, ..." format
                matches_mcc = re.findall(b'MCC\s+([0-9]+)', content)
                if matches_mcc:
                    extracted["NMCC"] = matches_mcc[-1].decode('utf-8', errors='ignore')

                matches_mnc = re.findall(b'MNC\s+([0-9]+)', content)
                if matches_mnc:
                    extracted["NMNC"] = matches_mnc[-1].decode('utf-8', errors='ignore')

                # SMCC and SMNC from "SMCC: 901" / "SMNC: 37" format
                matches_smcc = re.findall(b'SMCC:\s*([0-9]+)', content)
                if matches_smcc:
                    extracted["SMCC"] = matches_smcc[-1].decode('utf-8', errors='ignore')

                matches_smnc = re.findall(b'SMNC:\s*([0-9]+)', content)
                if matches_smnc:
                    extracted["SMNC"] = matches_smnc[-1].decode('utf-8', errors='ignore')

                # Network Provider from "QMI_NAS_EONS_NAME JIO 4G" format
                matches_eons = re.findall(b'QMI_NAS_EONS_NAME\s+(.+)', content)
                if matches_eons:
                    provider = matches_eons[-1].decode('utf-8', errors='ignore').strip()
                    if provider:
                        extracted["Network Provider"] = "Jio 4G" if "jio" in provider.lower() else provider

                # Fallback: PLMN{...} format for Network Provider
                if "Network Provider" not in extracted:
                    matches_plmn = re.findall(b'PLMN\{([^}]+)\}', content)
                    if matches_plmn:
                        for match in matches_plmn:
                            plmn_raw = match.decode('utf-8', errors='ignore')
                            parts = [p.strip() for p in plmn_raw.split(',')]
                            text_parts = [p for p in parts if p and p != '-' and not p.replace('-', '').isdigit()]
                            if text_parts:
                                extracted["Network Provider"] = text_parts[0]

    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        
    return results, extracted

def print_report(component: str, file_path: str, results: Dict[str, bool], extracted: Dict[str, str] = None):
    print(f"\n{'='*60}")
    print(f" ANALYSIS REPORT: {component}")
    print(f" File: {file_path}")
    print(f"{'='*60}")
    
    if not results and not extracted:
        print(" No results or file error.")
        return

    if extracted:
        for key, val in extracted.items():
            print(f" {key}: {val}")
        print(f"{'-'*60}")

    all_passed = all(results.values()) if results else False
    
    if results:
        for payload, found in results.items():
            status = "[PASS]" if found else "[FAIL]"
            # Truncate long payloads for display
            display_payload = (payload[:75] + '...') if len(payload) > 75 else payload
            print(f" {status} {display_payload}")
            
    print(f"{'-'*60}")
    if results and all_passed:
        print(f" VERDICT: {component} is HEALTHY. All expected payloads found.")
    else:
         print(f" VERDICT: No expected payloads evaluated.")
    print(f"{'='*60}\n")

def main():
    parser = argparse.ArgumentParser(description="Telematics AI Assistant")
    parser.add_argument("--product", choices=["IDCEVO", "IDC23"], default="IDCEVO", help="Product selection (IDCEVO or IDC23)")
    parser.add_argument("--inad", help="Path to INAD.dlt file (IDCEVO product)")
    parser.add_argument("--ibam", help="Path to IBAM.dlt file (IDCEVO product)")
    parser.add_argument("--idcevo", help="Path to IDCEVO.dlt file (IDCEVO product)")
    parser.add_argument("--idc", help="Path to IDC.dlt file (IDC23 product)")
    parser.add_argument("--wave", help="Path to WAVE.dlt file (IDC23 product)")

    args = parser.parse_args()
    
    product = args.product
    print(f"Product Selected: {product}")

    if product == "IDC23":
        idc_path = args.idc or FILE_PATHS.get("IDC")
        wave_path = args.wave or FILE_PATHS.get("WAVE")
 
        if not idc_path and not wave_path:
            print("Please provide at least one IDC23 log file (--idc or --wave).")
            print("Usage: python app.py --product IDC23 --idc <file> --wave <file>")
            return
 
        if idc_path:
            print(f"Analyzing IDC log: {idc_path}")
            results, extracted = analyze_file(idc_path, "IDC")
            print_report("IDC", idc_path, results, extracted)
 
        if wave_path:
            print(f"Analyzing WAVE log: {wave_path}")
            results, extracted = analyze_file(wave_path, "WAVE")
            print_report("WAVE", wave_path, results, extracted)
 
    else:
        inad_path = args.inad or FILE_PATHS.get("INAD")
        ibam_path = args.ibam or FILE_PATHS.get("IBAM")
        idcevo_path = args.idcevo or FILE_PATHS.get("IDCEVO")
 
        if not inad_path and not ibam_path and not idcevo_path:
            print("Please provide at least one IDCEVO log file (--inad, --ibam, or --idcevo).")
            print("Usage: python app.py --product IDCEVO --inad <file> --ibam <file> --idcevo <file>")
            return
 
        if inad_path:
            if "path\\to\\your" in inad_path:
                print("Warning: INAD path looks like a placeholder.")
            print(f"Analyzing INAD log: {inad_path}")
            results, extracted = analyze_file(inad_path, "INAD")
            print_report("INAD", inad_path, results, extracted)
 
        if ibam_path:
            if "path\\to\\your" in ibam_path:
                print("Warning: IBAM path looks like a placeholder.")
            print(f"Analyzing IBAM log: {ibam_path}")
            results, extracted = analyze_file(ibam_path, "IBAM")
            print_report("IBAM", ibam_path, results, extracted)
 
        if idcevo_path:
            if "path\\to\\your" in idcevo_path:
                print("Warning: IDCEVO path looks like a placeholder.")
            print(f"Analyzing IDCEVO log: {idcevo_path}")
            results, extracted = analyze_file(idcevo_path, "IDCEVO")
            print_report("IDCEVO", idcevo_path, results, extracted)
 
 
if __name__ == "__main__":
    main()
 
