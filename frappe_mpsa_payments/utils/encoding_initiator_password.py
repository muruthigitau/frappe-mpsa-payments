import frappe
import base64
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from datetime import datetime

def generate_security_credential(initiator_password: str, certificate_path: str) -> str:
    """
    Encrypts the initiator password using the uploaded M-Pesa public key certificate
    following M-Pesa's security credential generation requirements.
    """
    try:
        # Retrieve the File document from Frappe
        file_doc = frappe.get_doc("File", {"file_url": certificate_path})
        
        # Construct the absolute path
        full_path = file_doc.get_full_path()

        with open(full_path, "rb") as cert_file:
            # Load the X.509 certificate (supports both PEM & DER formats)
            cert_data = cert_file.read()

            if b"BEGIN CERTIFICATE" in cert_data:
                cert = x509.load_pem_x509_certificate(cert_data)
            else:
                cert = x509.load_der_x509_certificate(cert_data)

            # Extract the RSA public key from the certificate
            public_key = cert.public_key()

        # Encrypt the Base64-encoded password using RSA (PKCS#1 v1.5)
        encrypted_data = public_key.encrypt(
            initiator_password.encode("utf-8"),
            padding.PKCS1v15()  # Use PKCS#1.5 padding (not OAEP)
        )

        # Convert encrypted bytes to a Base64 string
        security_credential = base64.b64encode(encrypted_data).decode("utf-8")

        return security_credential

    except Exception as e:
        frappe.log_error(title="Security Credential Generation Error", message=str(e))
        raise frappe.ValidationError(f"Error generating security credential: {str(e)}")
