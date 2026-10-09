# Greenfield Secondary School Portal

A simple free school portal built with **Streamlit** + **SQLite**.

## Features

- 👨‍🎓 Student / Parent login (Student ID + PIN)
- 📊 View academic results
- 📥 Download Report Card as PDF
- 💰 View school fees & outstanding balance
- 💳 Pay school fees (demo mode + Paystack-ready)
- 🔐 Admin dashboard

## Demo Login

**Students (PIN for all is `1234`):**
- Student ID `1` → Amina Okello (Form 3)
- Student ID `2` → Brian Mwangi (Form 4)
- Student ID `5` → Elena Silva (Form 4) – already paid Term 1

**Admin:**
- Password: `admin123`

## How to Run Locally

```bash
pip install -r requirements.txt
streamlit run school_portal.py
```

## Deploy Free on Streamlit Community Cloud

1. Create a free GitHub account (if you don’t have one)
2. Create a new repository and upload these files:
   - `school_portal.py`
   - `requirements.txt`
   - `secondary_school.db` (optional – the app will create sample data automatically)
3. Go to [https://share.streamlit.io](https://share.streamlit.io)
4. Sign in with GitHub
5. Click **New app** → select your repository → set main file to `school_portal.py`
6. Click **Deploy**

Your app will be live at: `https://your-app-name.streamlit.app`

## Adding Real Paystack Payments Later

1. Create a free account at [paystack.com](https://paystack.com)
2. Get your **Public Key**
3. In Streamlit Cloud → App Settings → Secrets, add:

```toml
PAYSTACK_PUBLIC_KEY = "pk_live_xxxxxxxx"
```

Then the payment button can be upgraded to real Paystack checkout.

## Notes

- All data is stored in `secondary_school.db` (SQLite)
- Default PIN for every student is `1234` (change in real use)
- Admin password is `admin123` (change it!)
