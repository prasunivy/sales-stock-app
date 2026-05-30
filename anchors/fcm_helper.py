"""
fcm_helper.py
Place this in the anchors/ folder.
Sends Firebase Cloud Messaging push notifications to field staff.
"""

import requests
import streamlit as st
import google.auth
import google.auth.transport.requests
from google.oauth2 import service_account
from anchors.supabase_client import admin_supabase


def _get_access_token() -> str:
    """Get OAuth2 access token for FCM V1 API using service account."""
    try:
        firebase_config = dict(st.secrets["firebase"])
        credentials = service_account.Credentials.from_service_account_info(
            firebase_config,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"],
        )
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
        return credentials.token
    except Exception as e:
        st.error(f"FCM token error: {e}")
        return ""


def _get_fcm_token_for_user(user_id: str) -> str:
    """Get the FCM device token for a user from Supabase."""
    try:
        result = admin_supabase.table("user_fcm_tokens") \
            .select("token") \
            .eq("user_id", user_id) \
            .maybe_single() \
            .execute()
        if result.data:
            return result.data.get("token", "")
    except Exception as e:
        st.error(f"FCM token fetch error: {e}")
    return ""


def send_push_notification(
    user_id: str,
    title: str,
    body: str,
    data: dict = None,
) -> bool:
    """
    Send a push notification to a specific user.
    Returns True if successful, False otherwise.
    """
    try:
        device_token = _get_fcm_token_for_user(user_id)
        if not device_token:
            st.warning(f"No FCM token for user {user_id}")
            return False

        access_token = _get_access_token()
        if not access_token:
            return False

        project_id = st.secrets["firebase"]["project_id"]
        url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

        payload = {
            "message": {
                "token": device_token,
                "notification": {
                    "title": title,
                    "body": body,
                },
                "android": {
                    "notification": {
                        "channel_id": "ivy_pharma_channel",
                        "sound": "default",
                    },
                    "priority": "high",
                },
                "data": {k: str(v) for k, v in (data or {}).items()},
            }
        }

        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10,
        )

        if response.status_code == 200:
            # Save to user_notifications for My Activity screen
            try:
                admin_supabase.table("user_notifications").insert({
                    "user_id": user_id,
                    "title": title,
                    "body": body,
                    "type": (data or {}).get("type", ""),
                    "ops_no": (data or {}).get("ops_no", ""),
                }).execute()
            except Exception:
                pass
            return True
        else:
            st.error(f"FCM error: {response.status_code} {response.text}")
            return False

    except Exception as e:
        st.error(f"FCM send error: {e}")
        return False


def send_push_to_all_users(
    title: str,
    body: str,
    data: dict = None,
) -> int:
    """
    Send a push notification to ALL active users.
    Returns count of successful sends.
    """
    try:
        users = admin_supabase.table("user_fcm_tokens") \
            .select("user_id") \
            .execute()

        success = 0
        for user in (users.data or []):
            if send_push_notification(
                user["user_id"], title, body, data
            ):
                success += 1
        return success
    except Exception as e:
        print(f"FCM broadcast error: {e}")
        return 0


# ── Convenience functions for OPS events ─────────────────────

def notify_invoice_created(user_id: str, ops_no: str,
                            party_name: str, amount: float):
    send_push_notification(
        user_id=user_id,
        title="📄 New Invoice Created",
        body=f"{ops_no} | {party_name} | \u20b9{amount:,.0f}",
        data={"type": "invoice", "ops_no": ops_no},
    )


def notify_payment_created(user_id: str, ops_no: str,
                            party_name: str, amount: float):
    send_push_notification(
        user_id=user_id,
        title="\U0001f4b0 Payment Recorded",
        body=f"{ops_no} | {party_name} | \u20b9{amount:,.0f}",
        data={"type": "payment", "ops_no": ops_no},
    )


def notify_credit_note_created(user_id: str, ops_no: str,
                                party_name: str, amount: float):
    send_push_notification(
        user_id=user_id,
        title="\U0001f4dd Credit Note Created",
        body=f"{ops_no} | {party_name} | \u20b9{amount:,.0f}",
        data={"type": "credit_note", "ops_no": ops_no},
    )


def notify_invoice_cancelled(user_id: str, ops_no: str, party_name: str):
    send_push_notification(
        user_id=user_id,
        title="\u274c Invoice Cancelled",
        body=f"{ops_no} | {party_name}",
        data={"type": "invoice_cancelled", "ops_no": ops_no},
    )
