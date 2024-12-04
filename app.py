import streamlit as st
import pymongo
from pymongo import MongoClient
from twilio.rest import Client as TwilioClient
import smtplib
from email.mime.text import MIMEText
import random
import ssl

st.set_page_config(
    page_title="Payment Portal",
    page_icon="icon.png", 
    layout="centered",    
    initial_sidebar_state="collapsed"
)

hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# MongoDB Connection
client = MongoClient(st.secrets['MONGO_URI'])
db = client[st.secrets['MONGO_DB_NAME']]
clients_collection = db['clients']
transactions_collection = db['transactions']

# Twilio Configuration
twilio_client = TwilioClient(st.secrets['TWILIO_ACCOUNT_SID'], st.secrets['TWILIO_AUTH_TOKEN'])

def send_whatsapp_message(to_number, message):
    """
    Send WhatsApp message via Twilio
    """
    try:
        message = twilio_client.messages.create(
            from_=f'whatsapp:{st.secrets["TWILIO_PHONE_NUMBER"]}',
            body=message,
            to=f'whatsapp:{to_number}'
        )
        return True
    except Exception as e:
        st.error(f"Failed to send WhatsApp message: {e}")
        return False

def send_otp_email(email, otp):
    """
    Send OTP via SMTP
    """
    try:
        # Email configuration
        smtp_server = st.secrets['SMTP_SERVER']
        smtp_port = st.secrets['SMTP_PORT']
        sender_email = st.secrets['SENDER_EMAIL']
        sender_password = st.secrets['SENDER_PASSWORD']

        # Create message
        msg = MIMEText(f'Your OTP is: {otp}')
        msg['Subject'] = 'Login OTP for Payment Portal'
        msg['From'] = sender_email
        msg['To'] = email

        # Create secure context
        context = ssl.create_default_context()

        # Send email
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, email, msg.as_string())
        return True
    except Exception as e:
        st.error(f"Failed to send OTP: {e}")
        return False

def generate_random_otp():
    return f"{random.randint(100000, 999999)}"

def thank_you_page(name):
    """
    Render the thank-you page for the user.
    
    :param name: User's name to personalize the message
    """
    st.title("Thank You!")
    st.markdown(f"### Dear {name},")
    st.write(
        """
        We thank you for doing business with us! We hope you found our service exceptional and the 
        process seamless. Your support means a lot to us!
        """
    )
    st.write("**Interested in more projects or services? Let us help you achieve your goals.**")
    st.markdown("""
        - [Aniketh R](https://anikethvardhan.netlify.app)
        - [Md Waseel](https://mdwaseel.bewebfy.com)
    """)
    st.markdown("### We look forward to working with you again! 😊")
    st.balloons()

def main():
    st.title("Project Payment and Access Portal")

    # Initialize session state variables
    session_vars = ['stage', 'name', 'email', 'phone_number', 'transaction_id', 'generated_otp', 'client_details', 'project_link', 'payment_verification_otp', 'invoice_link']
    for var in session_vars:
        if var not in st.session_state:
            st.session_state[var] = None

    if st.session_state.stage is None:
        st.session_state.stage = 'login'

    # Login Stage
    if st.session_state.stage == 'login':
        st.header("Client Login")
        with st.form("client_login"):
            email = st.text_input("Email Address")
            phone_number = st.text_input("Phone Number")
            login_submit = st.form_submit_button("Send OTP")

            if login_submit:
                client = clients_collection.find({"email": email, "phone_number": phone_number})                
                if client:
                    otp = generate_random_otp()
                    st.session_state.generated_otp = otp
                    st.session_state.email = email
                    st.session_state.phone_number = phone_number
                    st.session_state.client_details = client

                    email_sent = send_otp_email(email, otp)
                    if email_sent:
                        st.session_state.stage = 'otp_verification'
                        st.rerun()
                    else:
                        st.error("Failed to send OTP. Please try again.")
                else:
                    st.error("Client not found. Please check your details.")

    # OTP Verification Stage
    elif st.session_state.stage == 'otp_verification':
        st.header("OTP Verification")
        with st.form("otp_verify"):
            otp_input = st.text_input("Enter OTP sent to your email")
            verify_otp = st.form_submit_button("Verify")

            if verify_otp:
                if otp_input == st.session_state.generated_otp:
                    st.session_state.stage = 'client_details'
                    st.rerun()
                else:
                    st.error("Incorrect OTP. Please try again.")

    # Client Dashboard
    elif st.session_state.stage == 'client_details':
        st.header("Client Dashboard")
        client = st.session_state.client_details
        st.write(f"**Name:** {client.get('name', 'N/A')}")
        st.write(f"**Email:** {client.get('email', 'N/A')}")
        st.write(f"**Phone Number:** {client.get('phone_number', 'N/A')}")
        st.write(f"**Project Name:** {client.get('project_name', 'N/A')}")
        st.write(f"**Due Amount:** ₹{client.get('due', 0.0)}")
        st.markdown(f"[Download Invoice]({st.session_state.invoice_link})")
                 
        if st.button("Proceed to Payment"):
            st.session_state.stage = 'payment'
            st.rerun()

    # Payment Stage
    elif st.session_state.stage == 'payment':
        st.header("Payment Details")
        amount = st.session_state.client_details.get('due', 0.0)

        if amount:
            upi_url = f"upi://pay?pa=your_upi_id&pn=Your Name&am={amount}&cu=INR"
            qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={upi_url}"
            
            # Center align the QR code
            col1, col2, col3 = st.columns([1,2,1])
            with col2:
                st.write(f"Scan the QR code below to pay ₹{amount}")
                st.image(qr_code_url)

        with st.form("payment_confirmation"):
            transaction_ref = st.text_input("Transaction Reference ID")
            submit_payment = st.form_submit_button("Submit Payment")

            if submit_payment:
                # Generate OTP for payment verification
                payment_verify_otp = generate_random_otp()
                st.session_state.payment_verification_otp = payment_verify_otp
                
                admin_message = f"""
                New Payment Submission:
                Name: {st.session_state.client_details.get('name')}
                Email: {st.session_state.client_details.get('email')}
                Amount: ₹{amount}
                Transaction Ref: {transaction_ref}
                OTP for Payment Verification: {payment_verify_otp}
                """
                send_whatsapp_message(st.secrets['ADMIN_PHONE_NUMBER'], admin_message)
                st.session_state.stage = 'payment_verification'
                st.rerun()

    # Payment Verification Stage
    elif st.session_state.stage == 'payment_verification':
        st.header("Payment Verification")
        with st.form("payment_verify_otp"):
            verification_otp = st.text_input("Enter OTP sent to Admin")
            verify_payment_otp = st.form_submit_button("Verify Payment")

            if verify_payment_otp:
                if verification_otp == st.session_state.payment_verification_otp:
                    st.session_state.stage = 'project_access'
                    st.rerun()
                else:
                    st.error("Incorrect OTP. Please try again.")

    # Project Access Stage
    elif st.session_state.stage == 'project_access':
        st.header("Project Access")
        download_link = st.session_state.project_link
        st.markdown(f"[Download Project]({download_link})")
        if st.button("Finish"):
            st.session_state.stage = 'thank_you'
            st.rerun()

    # Thank You Page
    elif st.session_state.stage == 'thank_you':
        thank_you_page(st.session_state.client_details.get('name', 'Client'))

if __name__ == "__main__":
    main()
