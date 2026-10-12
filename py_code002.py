# Testing for GitHub Version Control 2026/10/12 15:52 Fix Bug
# 修正測試
import csv
from datetime import datetime, timedelta
import json
from zoneinfo import ZoneInfo
import requests

# ==============================================================================
# 1. 設定區：請將以下資訊替換為您在 SAP BTP Service Key 中取得的真實資料
# ==============================================================================
CLIENT_ID = "Client ID Copy from Audit log mamagement Service Key"
CLIENT_SECRET = "Same as above"
AUTH_URL = "https://AUTH_URL/oauth/token"
SERVICE_URL = "https://Service_URL"


# ==============================================================================
# 2. 功能函式區
# ==============================================================================
def get_access_token(auth_url, client_id, client_secret):
    """獲取 OAuth2 Access Token"""
    token_url = f"{auth_url}/oauth/token"
    payload = {"grant_type": "client_credentials"}
    try:
        response = requests.post(
            token_url, data=payload, auth=(client_id, client_secret), timeout=10
        )
        response.raise_for_status()
        return response.json().get("access_token")
    except requests.exceptions.RequestException as e:
        print(f"❌ 獲取 Token 失敗: {e}")
        return None


def fetch_audit_logs(service_url, token, time_from, time_to):
    """呼叫 API 抓取日誌"""
    api_url = f"{service_url}/auditlog/v2/auditlogrecords"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    params = {"time_from": time_from, "time_to": time_to}

    try:
        response = requests.get(api_url, headers=headers, params=params, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ 抓取日誌失敗: {e}")
        return None


def parse_tw_to_utc_iso(time_str):
    """將台灣時間輸入轉為 SAP 專用無 'Z' 結尾的 UTC 字串"""
    cleaned_str = time_str.strip().replace("T", " ")
    formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]

    for fmt in formats:
        try:
            naive_dt = datetime.strptime(cleaned_str, fmt)
            tw_dt = naive_dt.replace(tzinfo=ZoneInfo("Asia/Taipei"))
            utc_dt = tw_dt.astimezone(ZoneInfo("UTC"))
            return utc_dt.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    return None


def export_parsed_messages_to_csv(logs, filename="sap_audit_logs.csv"):
    """💡 直接解析並攤平 Raw Message 內容匯出為 CSV"""
    if not logs:
        print("📭 沒有資料可供匯出。")
        return

    # 定義經由 Raw Message 解析拆解後的乾淨欄位
    fieldnames = [
        "事件時間 (台灣時間 UTC+8)",
        "事件UUID (Event UUID)",
        "操作人員 (User)",
        "異動主體類型 (Object Type)",
        "執行動作 (Action)",
        "異動目標名稱 (Target Name)",
        "執行結果 (Success)",
        "稽核分類 (Category)",
        "租戶ID (Tenant ID)",
    ]

    try:
        with open(
            filename, mode="w", encoding="utf-8-sig", newline=""
        ) as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()

            for log in logs:
                raw_msg = log.get("message", "{}")

                # 初始化預設值
                msg_uuid, user, tw_time_str, success = "", "", "", ""
                obj_type, action, target_name, category, tenant = (
                    "",
                    "",
                    "",
                    "",
                    "",
                )

                # 💡 開始直接解析 Raw Message 的內嵌 JSON 內容
                try:
                    msg_json = json.loads(raw_msg)

                    # 基礎資訊解析
                    msg_uuid = msg_json.get("uuid", "")
                    user = msg_json.get("user", "")
                    success = msg_json.get("success", "")
                    category = msg_json.get("category", "")
                    tenant = msg_json.get("tenant", "")

                    # 處理時間 (將日誌內部的 UTC 時間轉為台灣時間字串)
                    raw_time = msg_json.get("time", "")
                    if raw_time:
                        clean_time = raw_time.split(".")[0].replace("Z", "")
                        utc_dt = datetime.strptime(
                            clean_time, "%Y-%m-%dT%H:%M:%S"
                        )
                        tw_time_str = (utc_dt + timedelta(hours=8)).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )

                    # 物件細項解析 (Object 節點)
                    obj_data = msg_json.get("object", {})
                    obj_type = obj_data.get("type", "")

                    # 物件 ID 細項解析 (Id 節點)
                    obj_id_details = obj_data.get("id", {})
                    action = obj_id_details.get("crudType", "")

                    # 根據不同的日誌結構動態抓取目標物件名稱
                    target_name = (
                        obj_id_details.get("rolecollection_name", "")
                        or obj_id_details.get("name", "")
                        or obj_id_details.get("tableName", "")
                    )

                except Exception:
                    # 如果 raw message 不是標準 JSON，則保留外層日誌的原始文字代替
                    user = log.get("user", "")
                    category = log.get("category", "")
                    tw_time_str = log.get("time", "")

                # 寫入拆解後的乾淨欄位資料
                writer.writerow(
                    {
                        "事件時間 (台灣時間 UTC+8)": tw_time_str,
                        "事件UUID (Event UUID)": msg_uuid,
                        "操作人員 (User)": user,
                        "異動主體類型 (Object Type)": obj_type,
                        "執行動作 (Action)": action,
                        "異動目標名稱 (Target Name)": target_name,
                        "執行結果 (Success)": success,
                        "稽核分類 (Category)": category,
                        "租戶ID (Tenant ID)": tenant,
                    }
                )

        print(
            f"💾 Raw Message 解析完成！乾淨報表已儲存至：【{filename}】"
        )
    except Exception as e:
        print(f"❌ 匯出 CSV 失敗: {e}")


# ==============================================================================
# 3. 主程式執行邏輯
# ==============================================================================
if __name__ == "__main__":
    print("=== SAP BTP Audit Log 工具 (Raw Message 自動解析版) ===")

    print("\n[請輸入台灣時間] 格式範例: 2026-09-21 14:00:00")
    tw_start = input("➡️ 請輸入【開始】時間: ")
    tw_end = input("➡️ 請輸入【結束】時間: ")

    utc_start = parse_tw_to_utc_iso(tw_start)
    utc_end = parse_tw_to_utc_iso(tw_end)

    if utc_start and utc_end:
        print("\n🔄 正在向 SAP BTP 驗證身分...")
        access_token = get_access_token(AUTH_URL, CLIENT_ID, CLIENT_SECRET)

        if access_token:
            print("✅ 成功取得 Access Token！")
            print("📅 正在發送 API 請求抓取日誌中...")

            logs = fetch_audit_logs(SERVICE_URL, access_token, utc_start, utc_end)

            if logs:
                print(f"🎉 成功抓取到 {len(logs)} 筆原始日誌！")
                print("🔄 正在深入解析 Raw Message 並轉為乾淨欄位...")
                export_parsed_messages_to_csv(logs, filename="sap_audit_logs.csv")
            else:
                print("📭 該時段內沒有符合的日誌資料，未產生報表。")
    else:
        print("❌ 時間解析失敗，程式結束。")
