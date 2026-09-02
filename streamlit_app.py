import streamlit as st
import pandas as pd
import os
import tempfile
from app import analyze_file, EXPECTED_PAYLOADS

st.set_page_config(page_title="Telematics AI Assistant", layout="wide", page_icon="📝")

st.title("📝 Telematics AI Assistant")
st.markdown("Upload your component `.dlt` logs to verify ECU IDs and analyze diagnostic payloads securely.")

st.markdown("---")

# Product Selection
st.subheader("1. Select Product")
selected_product = st.radio("Select Target Product:", ["IDCEVO", "IDC23", "PENT(CDE/RSE)"], horizontal=True, key="product_selection")

st.markdown("---")

# Dynamic Layout for uploading files based on selected product
st.subheader(f"2. Upload {selected_product} Log Files")

if selected_product == "IDC23":
    st.info("📤 Upload the **WAVE** and/or **IDC** `.dlt` log file(s). " \
            " 1. Start the respective traces through DTL Viewer. " \
            " 2. Perform IDC STEUERGRAETE_RESET. " \
            " 3. Wait till the screen ups and perform the provisioning via CD Store. " \
            " 4. Stop the traces and upload the logs here.")
    col1, col2 = st.columns(2)
    uploaded_wave = col1.file_uploader("Upload WAVE Log (.dlt)", type=["dlt"], key="wave")
    uploaded_idc = col2.file_uploader("Upload IDC Log (.dlt)", type=["dlt"], key="idc")
    uploaded_inad, uploaded_ibam, uploaded_idcevo = None, None, None
else:
    # IDCEVO and PENT(CDE/RSE) share identical upload/analysis logic, only the interface labels differ.
    st.info("📤 Upload the **INAD**, **IBAM** and/or **IDCEVO** `.dlt` log file(s). Steps to collect the traces -" \
    " 1. Start the respective traces through DTL Viewer. " \
    " 2. Perform IDCEVO STEUERGRAETE_RESET. " \
    " 3. Wait till the screen ups and perform the provisioning via CD Store. " \
    " 4. Stop the traces and upload the logs here.")
    col1, col2, col3 = st.columns(3)
    uploaded_inad = col1.file_uploader("Upload INAD Log (.dlt)", type=["dlt"], key="inad")
    uploaded_ibam = col2.file_uploader("Upload IBAM Log (.dlt)", type=["dlt"], key="ibam")
    uploaded_idcevo = col3.file_uploader("Upload IDCEVO Log (.dlt)", type=["dlt"], key="idcevo")
    uploaded_idc, uploaded_wave = None, None
with st.sidebar:
    st.header("ℹ️ Help & Instructions")

    tab_about, tab_upload, tab_results, tab_faq = st.tabs(["🔍 About", "📤 Upload", "📊 Results", "❓ FAQ"])

    with tab_about:
        st.markdown("**Telematics AI Assistant**")
        st.caption("Explore what the analyzer checks and how to use the results.")

        about_topic = st.selectbox(
            "Explore a topic",
            ["What this tool does", "What it checks", "How to read results"],
            key="about_topic"
        )

        if about_topic == "What this tool does":
            st.info(
                "Upload DLT diagnostic logs, verify the expected ECU payloads, "
                "and surface the extracted information needed for troubleshooting."
            )
            st.metric("Supported log format", ".dlt")
        elif about_topic == "What it checks":
            st.success("The analyzer checks the areas below in the uploaded traces.")
            for check in [
                "Certificates and TLS connectivity",
                "ECU identity and software versions",
                "VLAN, IPsec, and MACsec connectivity",
                "Network registration and signal quality",
                "MQTT/backend communication and provisioning state",
            ]:
                st.checkbox(check, value=True, disabled=True, key=f"about_check_{check}")
        else:
            st.warning("Use the result panels together with the extracted information.")
            with st.expander("Payload status", expanded=True):
                st.write("Green entries indicate an expected payload was found. Expand a failed entry to see the detected error or suggested solution.")
            with st.expander("Extracted information"):
                st.write("Review VIN, software versions, environment, provisioning state, network details, and signal measurements.")
        

    with tab_upload:
        st.markdown("Follow these steps:")
        st.checkbox("1. Select target product (IDCEVO, IDC23 or PENT(CDE/RSE))", value=bool(selected_product), disabled=True, key="help_step1")
        if selected_product == "IDC23":
            step2_done = bool(uploaded_wave or uploaded_idc)
            st.checkbox("2. Upload WAVE and/or IDC log (.dlt)", value=step2_done, disabled=True, key="help_step2")
        else:
            step2_done = bool(uploaded_inad or uploaded_ibam or uploaded_idcevo)
            st.checkbox("2. Upload INAD, IBAM and/or IDCEVO log (.dlt)", value=step2_done, disabled=True, key="help_step2")
        st.checkbox("3. Click 'Run Analysis'", value=False, disabled=True, key="help_step3")
        st.progress(1.0 if step2_done else 0.5 if selected_product else 0.0)
        if step2_done:
            st.success("Files ready — scroll down and click **Run Analysis**! 🎉")
        else:
            st.info("Upload at least one log file to continue.")

    with tab_results:
        st.markdown("""
        - ✅ **Green** — expected payload found.
        - ❌ **Red/expandable** — payload missing or a negative (error) payload was detected. Expand for details and a fix.
        - **Information** panel — summarizes extracted values (VIN, versions, signal level, etc.).
        - **Signal Graph** — RSSI/RSRP/RSRQ trend with a threshold reference table.
        """)

    with tab_faq:
        with st.expander("What file types are supported?"):
            st.caption("Only `.dlt` files are supported.")
        with st.expander("Can I upload multiple files at once?"):
            st.caption("Yes — logs from different components are combined into one unified result.")
        with st.expander("Why is my graph limited to 500 points?"):
            st.caption("Large logs are trimmed to the most recent 500 samples for readability.")

st.markdown("---")

def process_file(uploaded_file, component_name):
    if uploaded_file is not None:
        # Write to temp file safely to interface with app.py's file_path inputs
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dlt") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name
            
        try:
            results, extracted = analyze_file(tmp_path, component_name)
            return results, extracted
        finally:
            os.unlink(tmp_path)
    return None, None

def display_results(results, extracted, component_name):
    if not results and not extracted:
        st.warning("No results computed or file read error occurred.")
        return

    if "Valid ECUID" in results and not results["Valid ECUID"]:
        st.error(f"❌ Invalid ECUID Format. File does not match {component_name}.")
        return

    # Display individual payload evaluations
    st.markdown("**📋 Payload Verification:**")
    
    all_passed = True
    
    for payload, meta in results.items():
        if payload == "Valid ECUID":
            continue
            
        if isinstance(meta, bool):
            found = meta
            friendly_name = payload[:60] + '...' if len(payload) > 60 else payload
            neg_found = False
            pos_payload = payload
            neg_payload = ""
            solution = "[Solution Pending]"
        else:
            found = meta.get("positive_found", False)
            friendly_name = meta.get("name", payload)
            neg_found = meta.get("negative_found", False)
            pos_payload = meta.get("positive_payload", payload)
            neg_payload = meta.get("negative_payload", "")
            solution = meta.get("solution", "[Solution Pending]")

        # Show friendly name, expand to show full payload
        if found:
            st.markdown(f"✅ **{friendly_name}**")
        else:
            all_passed = False
            with st.expander(f"❌ {friendly_name}"):
                if neg_found:
                    st.markdown(f"""
                        <div style="background-color:rgba(255, 99, 71, 0.1); padding: 15px; border-radius: 8px; border: 1px solid rgba(255, 99, 71, 0.4);">
                            <h4 style="margin-top:0px; color:#ff4b4b;">⚠️ Negative Scenario Detected</h4>
                            <p style="margin-bottom:4px; font-size:14px;"><strong>Actual (Found Error Payload):</strong></p>
                            <code style="display:block; padding:8px; border-radius:4px; margin-bottom:15px; background:rgba(255,0,0,0.05); color:#d32f2f; border-left:3px solid #ff4b4b;">{neg_payload}</code>
                            <p style="margin-bottom:0px; font-size:14px;"><strong>💡 Possible Solution:</strong> {solution}</p>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.warning("Expected payload was missing entirely. No error logs were surfaced.")
                    st.caption(f"💡 **Debugging Solution:** {solution}")
                    
    st.markdown("---")
    if all_passed and results:
        st.success(f"🎉 **VERDICT: {component_name} is HEALTHY. All expected payloads found.**")
    else:
        st.error(f"⚠️ **VERDICT: {component_name} issues detected. Missing payloads.**")


def render_information_section(combined_extracted):
    if not combined_extracted:
        return

    with st.container():
        st.markdown("### 📌 Information")
        col1, col2 = st.columns(2)
        
        col1_keys = ["VIN", "ICON Version", "IDCEVO Version", "IDC Version", "WAVE Version", "Signal Level", "Current State", "Environment"]
        col2_keys = ["NMCC", "NMNC", "SMCC", "SMNC", "Network Provider"]
        
        for k in col1_keys:
            if k in combined_extracted:
                val = combined_extracted[k]
                display_text = f"**{k}:** {val}"
                
                if k == "Signal Level" and "Not Found" not in val and "Failed" not in val:
                    v_lower = val.lower()
                    if "poor" in v_lower:
                        bars = "🔴 ⚪ ⚪ ⚪"
                    elif "good" in v_lower:
                        bars = "🟡 🟡 ⚪ ⚪"
                    elif "great" in v_lower:
                        bars = "🟢 🟢 🟢 ⚪"
                    elif "excellent" in v_lower:
                        bars = "🟢 🟢 🟢 🟢"
                    else:
                        bars = "📶"
                    display_text = f"**{k}:** {bars} *({val})*"

                if "Not Found" in val or "Failed" in val:
                    col1.error(display_text)
                else:
                    col1.info(display_text)
                    
        for k in col2_keys:
            if k in combined_extracted:
                val = combined_extracted[k]
                display_text = f"**{k}:** {val}"
                if "Not Found" in val or "Failed" in val:
                    col2.error(display_text)
                else:
                    col2.info(display_text)

        for k, val in combined_extracted.items():
            if k not in col1_keys and k not in col2_keys and k != "Cell_Info_DF":
                display_text = f"**{k}:** {val}"
                if "Not Found" in val or "Failed" in val:
                    col2.error(display_text)
                else:
                    col2.info(display_text)

        if "Cell_Info_DF" in combined_extracted:
            st.markdown("### 📊 Signal Graph")
            df = pd.DataFrame(combined_extracted["Cell_Info_DF"])
            df = df[["RSSI", "RSRP", "RSRQ"]].apply(pd.to_numeric, errors="coerce")
            df = df.dropna(how="all")
            if df.empty:
                st.warning("No numeric RSSI, RSRP, or RSRQ values were found.")
                return

            with st.expander("📋 RSSI / RSRP / RSRQ Threshold Reference"):
                threshold_df = pd.DataFrame([
                    {"Metric": "RSRP", "Excellent": "≥ -80 dBm", "Good": "-90 to -80 dBm", "Fair/Weak": "-100 to -90 dBm", "Poor/Marginal": "< -100 dBm"},
                    {"Metric": "RSSI", "Excellent": "≥ -60 dBm", "Good": "-70 to -60 dBm", "Fair/Weak": "-80 to -70 dBm", "Poor/Marginal": "< -80 dBm"},
                    {"Metric": "RSRQ", "Excellent": "≥ -10 dB", "Good": "-15 to -10 dB", "Fair/Weak": "-20 to -15 dB", "Poor/Marginal": "< -20 dB"},
                ])
                st.dataframe(threshold_df, use_container_width=True, hide_index=True)

            # Keep the graph readable for very large logs.
            df = df.tail(500)

            import plotly.express as px
            
            full_names = {
                'RSRP': 'RSRP (Reference Signal Received Power)',
                'RSSI': 'RSSI (Received Signal Strength Indicator)',
                'RSRQ': 'RSRQ (Reference Signal Received Quality)'
            }
            df_full = df.rename(columns=full_names)
            df_reset = df_full.reset_index(drop=True)
            df_reset['Occurrence'] = df_reset.index
            
            value_columns = list(full_names.values())
            df_melted = df_reset.melt(id_vars='Occurrence', value_vars=value_columns, var_name='Metric', value_name='Value')
            
            def get_quality(row):
                m = row['Metric']
                v = row['Value']
                if m.startswith('RSRP'):
                    if v >= -80: return 'Excellent'
                    elif v >= -90: return 'Good'
                    elif v >= -100: return 'Fair/Weak'
                    else: return 'Poor/Marginal'
                elif m.startswith('RSSI'):
                    if v >= -60: return 'Excellent'
                    elif v >= -70: return 'Good'
                    elif v >= -80: return 'Weak'
                    else: return 'Poor'
                elif m.startswith('RSRQ'):
                    if v >= -10: return 'Excellent'
                    elif v >= -15: return 'Good'
                    elif v >= -20: return 'Fair/Poor'
                    else: return 'Bad/No signal'
                return ''
                
            df_melted['Quality Rating'] = df_melted.apply(get_quality, axis=1)
            
            fig = px.line(df_melted, x='Occurrence', y='Value', color='Metric', height=600,
                          hover_data={'Occurrence': False, 'Metric': False, 'Value': True, 'Quality Rating': True})
            fig.update_layout(hovermode='x unified')
            st.plotly_chart(fig, use_container_width=True)


st.subheader("3. Analyze Logs")
if st.button("Run Analysis"):
    if selected_product == "IDC23":
        if not (uploaded_idc or uploaded_wave):
            st.warning("Please upload at least one IDC23 log file (IDC or WAVE) above to begin analysis.")
        else:
            with st.spinner("Analyzing uploaded IDC23 logs..."):
                idc_res, idc_ext = process_file(uploaded_idc, "IDC")
                wave_res, wave_ext = process_file(uploaded_wave, "WAVE")

                combined_extracted = {}
                for comp_name, ext in [("IDC", idc_ext), ("WAVE", wave_ext)]:
                    if ext:
                        for k, v in ext.items():
                            if k in ("Environment", "Current State") and comp_name != "IDC":
                                continue
                            if k == "Cell_Info_DF":
                                existing = combined_extracted.get("Cell_Info_DF", [])
                                combined_extracted[k] = existing + v
                            else:
                                combined_extracted[k] = str(v)

                render_information_section(combined_extracted)

                st.markdown("---")
                res_col1, res_col2 = st.columns(2)
                with res_col1:
                    st.subheader("🔍 WAVE Analysis")
                    if uploaded_wave:
                        display_results(wave_res, wave_ext, "WAVE")
                    else:
                        st.warning("⚠️ WAVE log file is missing.")
                with res_col2:
                    st.subheader("🔍 IDC Analysis")
                    if uploaded_idc:
                        display_results(idc_res, idc_ext, "IDC")
                    else:
                        st.warning("⚠️ IDC log file is missing.")
    else:
        if not (uploaded_inad or uploaded_ibam or uploaded_idcevo):
            st.warning(f"Please upload at least one {selected_product} log file above to begin analysis.")
        else:
            with st.spinner(f"Analyzing uploaded {selected_product} logs..."):
                # Process files first to extract all info
                inad_res, inad_ext = process_file(uploaded_inad, "INAD")
                ibam_res, ibam_ext = process_file(uploaded_ibam, "IBAM")
                idcevo_res, idcevo_ext = process_file(uploaded_idcevo, "IDCEVO")
                
                # Combine extracted info
                combined_extracted = {}
                for comp_name, ext in [("INAD", inad_ext), ("IBAM", ibam_ext), ("IDCEVO", idcevo_ext)]:
                    if ext:
                        for k, v in ext.items():
                            if k == "Cell_Info_DF":
                                existing = combined_extracted.get("Cell_Info_DF", [])
                                combined_extracted[k] = existing + v
                            else:
                                combined_extracted[k] = str(v)
                            
                render_information_section(combined_extracted)
                
                # Render component specific payload analysis
                st.markdown("---")
                res_col1, res_col2, res_col3 = st.columns(3)
                with res_col1:
                    st.subheader("🔍 INAD Analysis")
                    if uploaded_inad:
                        display_results(inad_res, inad_ext, "INAD")
                    else:
                        st.warning("⚠️ INAD log file is missing.")
                with res_col2:
                    st.subheader("🔍 IBAM Analysis")
                    if uploaded_ibam:
                        display_results(ibam_res, ibam_ext, "IBAM")
                    else:
                        st.warning("⚠️ IBAM log file is missing.")
                with res_col3:
                    st.subheader("🔍 IDCEVO Analysis")
                    if uploaded_idcevo:
                        display_results(idcevo_res, idcevo_ext, "IDCEVO")
                    else:
                        st.warning("⚠️ IDCEVO log file is missing.")

st.markdown("---")
st.subheader("4. Support")
st.markdown("If you are still unable to resolve the issue or need further technical assistance, please raise the request by creating a ticket.")

# Fallback for Streamlit versions < 1.27.0
jira_button_html = """
<a href="https://jira.cc.bmwgroup.net/browse/LTTSTM-133259" target="_blank">
    <div style="display: inline-block; background-color: #FF4B4B; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: bold; cursor: pointer; border: 1px solid #FF4B4B;">
        🛠️ Create JIRA Ticket
    </div>
</a>
"""
st.markdown(jira_button_html, unsafe_allow_html=True)
