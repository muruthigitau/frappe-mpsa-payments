## 📲 Frappe Mpesa Payments  

Frappe Mpesa Payments is a custom [Frappe](https://frappe.io/framework) application that integrates with [Safaricom's Daraja API](https://developer.safaricom.co.ke/). It is built to extend [ERPNext](https://frappe.io/erpnext) enabling seamless mobile money payments from customers, and payment disbursements to suppliers and employees. Hence it implements the following APIs: Mpesa Express (STK Push), C2B (Customer to Business), B2C (Business to Customer) and Transaction Status (Query status of payment).

---

## 🚀 Project Overview

This app was built to enable Kenyan businesses to automate and streamline payment collection, salary disbursement, and transaction tracking through Safaricom Mpesa — without leaving their ERP system.

### Supported APIs:
- ✅ **Mpesa Express (STK Push)**
- ✅ **C2B (Customer to Business)**
- ✅ **B2C (Business to Customer)**
- ✅ **Transaction Status (Query status of payment)**

### Use Cases:
#### 1. Mpesa Express (STK Push)
  - Request payment from Sales Invoices, Sales Order from the customer.
  ![mpesa_express_sales_order_and_invoice](https://github.com/user-attachments/assets/59129a80-d1f7-4638-9658-2c5dd48e30ff)
  - POS (Point of Sale)
  ![mpesa_express_pos](https://github.com/user-attachments/assets/16ed5cf0-89fe-44fe-aa05-16ee2d265add)
  - Webshop (E-Commerce)
  ![mpesa_express_webshop](https://github.com/user-attachments/assets/d56b053e-3ad8-4965-8587-a090484b445b)


#### 2. C2B (Customer to Business)
  - Receive payments from customers in real-time and reconcile with invoices.
  ![mpesa_c2b_sales_invoice](https://github.com/user-attachments/assets/ce7fdc6e-4e4a-44f1-a759-e411ac99f13a)

#### 3. B2C (Business to Customer)
  -  Disburse payments to suppliers to pay for Purchase Invoices and Purchase Orders
  ![b2c_disbursement_purchase_order_and_invoice](https://github.com/user-attachments/assets/b37f03a9-da9b-4a31-a6a2-90c30938062d)
  - Disburse money to your employees
    - Expense claims
     ![b2c_disbursement_expense_claim](https://github.com/user-attachments/assets/4eda92c2-b8b3-4784-9260-d91cf9de99db)
    - Employee Advances
    ![b2c_disbursement_employee_advance](https://github.com/user-attachments/assets/7875b2ad-ad36-4f06-8ff5-7a10a98e349b)
    - Salary 
    ![b2c_disbursement_salary_slip](https://github.com/user-attachments/assets/8207bf8e-ac72-4d43-a627-0e5a1e452d92)

#### 4. Query transaction status for failed/delayed payments.
#### 5. Log and audit incoming/outgoing C2B and B2C transactions.

---

## Table of Contents
- [📲 Frappe Mpesa Payments](#-frappe-mpesa-payments)
- [🚀 Project Overview](#-project-overview)
  - [Supported APIs:](#supported-apis)
  - [Use Cases:](#use-cases)
    - [1. Mpesa Express (STK Push)](#1-mpesa-express-stk-push)
    - [2. C2B (Customer to Business)](#2-c2b-customer-to-business)
    - [3. B2C (Business to Customer)](#3-b2c-business-to-customer)
    - [4. Query transaction status for failed/delayed payments.](#4-query-transaction-status-for-faileddelayed-payments)
    - [5. Log and audit incoming/outgoing C2B and B2C transactions.](#5-log-and-audit-incomingoutgoing-c2b-and-b2c-transactions)
- [Table of Contents](#table-of-contents)
- [🔑 Features](#-features)
- [🛠️ Installation](#️-installation)
  - [Managed Hosting](#managed-hosting)
  - [Self Hosting](#self-hosting)
- [⚙️ Configuration](#️-configuration)
- [🤵🏿 Usage Guide](#-usage-guide)
  - [1. 🔁 Trigger STK Push (Mpesa Express)](#1--trigger-stk-push-mpesa-express)
  - [2. 📥 Receive C2B Payments](#2--receive-c2b-payments)
    - [Notes:](#notes)
    - [FAQs: What happens when Registration Fails?](#faqs-what-happens-when-registration-fails)
  - [3. 💸 Disburse B2C Payments (Business to Customer)](#3--disburse-b2c-payments-business-to-customer)
    - [🧾Accounting Entries](#accounting-entries)
    - [Use Cases](#use-cases-1)
  - [4. 🔍 Reconcile Payments](#4--reconcile-payments)
  - [5. ❓Query Transaction Status](#5-query-transaction-status)
    - [Use Cases:](#use-cases-2)
- [Key DocTypes](#key-doctypes)
- [🔐 Security](#-security)
- [🛠️ Troubleshooting](#️-troubleshooting)

---

## 🔑 Features
- **STK Push (Mpesa Express):** Trigger an STK push from Payment Requests.
- **C2B Integration:** Receive and log incoming payments from customers automatically.
- **B2C Payments:** Send funds to employees or vendors and generate accounting entries.
- **Transaction Status Lookup:** Query historical Mpesa transactions via API.
- **Mpesa Settings:** Configure all Daraja credentials and certificates in one place.
- **Payment Reconciliation Tool:** Match C2B payments to outstanding invoices.
- **Webhook URL Registration:** Register your confirmation & validation URLs from within the system.
- **Public Key Management:** Upload & store certificates for secure B2C encryption.

---

## 🛠️ Installation
✅ Dependencies
- Frappe Framework
- ERPNext
- Valid Daraja API credentials
- Publicly accessible domain (for webhook callbacks)
N/B Must be *https://*

### Managed Hosting
If you are using [Frappe Cloud](https://frappecloud.com/)
1. Login in to your Frappe Cloud account.
2. Navigate to your Sites/Bench Groups dashboard.
3. Go to the **Apps** tab and select **+ Install App** / **+ Add App**.
4. Search for **Frappe Mpesa Payments** application in the [Marketplace](https://frappecloud.com/marketplace/search) section.
5. Or select **Add from Github** then add this github url ```https://github.com/navariltd/frappe-mpsa-payments.git``` Fetch Branches

### Self Hosting
1. Ensure you have a working Frappe and ERPNext instance
2. Clone this repository into your Frappe bench apps directory.
3. Go to the [Marketplace]
 ``` 
 bench get-app https://github.com/navariltd/frappe-mpsa-payments.git
 ```

 3. Install the app into your site
 ``` 
 bench --site [your-site-name] install-app frappe_mpsa_payments
 ```

---

## ⚙️ Configuration
<h4>Mpesa Settings</h4>

In the Mpesa Workspace or using the Awesome Search navigate to **Mpesa Settings**
This DocType is central to configuring Safaricom's Daraja API credentials, it is the entry point of various Mpesa payment services (Mpesa Express, C2B, and B2C). It holds the necessary credentials and identifiers for authentication and payment initiation.

To get these credentials you need to have an account on [Safaricom Developer Portal](https://developer.safaricom.co.ke/) and have a live/prod application that corresponds to the Business Shortcode you own (Paybill/Till Number). Contact [M-Pesa Business](mailto:m-pesabusiness@safaricom.co.ke) or [Safaricom API Support](mailto:api@safaricom.co.ke) for help in setting this up.

1. **API Type:**  Select the type of Mpesa API integration you’re setting up (Mpesa Express, C2B, or B2C).
2. **Consumer Key:** A unique key provided by Safaricom to authenticate API calls.
3. **Consumer Secret:** A secret code paired with the Consumer Key to secure API access.
4. **Security Credential:** Encryption credential used for additional security, particularly in B2C transactions.
5. **Till Number:** Identifier for C2B payments, where customers make payments directly to a till.
6. **Business Shortcode:** A unique code used to identify your business account in the Mpesa system.
7. **Online PassKey:** An additional authentication key, specifically for initiating Mpesa Express (STK Push) transactions.
8. **Initiator Name:** Operator name for API Operator in the [Mpesa Org Portal](https://org.ke.m-pesa.com).
9. **Initiator Password:** Password paired with the Initiator Name.

![Screenshot from 2024-10-30 15-55-09](https://github.com/user-attachments/assets/f786501f-5c5d-4c27-9a62-ba3d76ce9562)

---

## 🤵🏿 Usage Guide

### 1. 🔁 Trigger STK Push (Mpesa Express)

Mpesa Express (STK Push) is initiated through the **Payment Request** DocType in ERPNext.

**🔧 How it works:**
1. Create a new Payment Request either from Sales Invoice or Sales Order.
2. Set the **Mode of Payment** that is linked to your **Mpesa Settings**.
3. Since the **Payment Channel** is `Phone`
4. Enter the Customer's Phone Number in the **To** field
5. Save the Payment Request

👉🏿 Once saved, the system automatically triggers an **STK Push** request to the customer. When the customer finishes the transaction i.e., enters pin the Payment Request is completed and a Payment Entry created against the transaction.

**Can be used from:**
- Sales Invoice
- Sales Order
- POS
- Webshop

--TODO: Insert GIF Here

### 2. 📥 Receive C2B Payments

C2B (Customer to Business) integration enables your system to receive and log incoming payments from customers in real-time.

**🔧 How it Works**
1. Register URLs:
  - Navigate to **Mpesa C2B Payment Register URL**.
  - Link to your configured **Mpesa Settings** and its **Mode of Payment**.
  - Save the Document.
  - The Register Status should change to **Success** to indicate the callbacks have been registered.

2. Payment Logging:
  - Ensure the callbacks have been registered successfully.
  - Once a customer pays via your PayBill/Till, Daraja sends a callback to your registered URLs.
  - These callbacks are recorded in the **Mpesa C2B Payment Register**.

--TODO: Insert GIF Here

#### Notes:
- **Smart Matching Logic:**  
  - If Customer inputs a Sales Invoice Number or Customer Name that exists in your ERPNext instance, as the Account Number when making a Paybill payment, Daraja API will send this information as BillRefNumber in the callback.
  - If this information matches a Customer Name/Invoice Number in the system, then the Customer field is automatically filled in the Mpesa Payment Register. 
- **Auto-Reconciliaton Logic:**
  - In the **Mpesa Settings** there is an option **Auto Reconcile C2B Payments**.
  - If this is checked then once you submit the Mpesa Payment Record it will try to match an invoice if no invoice is found then a reconciliation of the customer's outstanding invoices will be performed automatically using FIFO logic.
  

#### FAQs: What happens when Registration Fails?

--TODO: Insert data here


### 3. 💸 Disburse B2C Payments (Business to Customer)

Use this feature to send money directly to employees or suppliers via **Mpesa B2C** integration.

**🔧 How It Works:**
1. Navigate to the **B2C Payment Disbursement** using the Awesome Search
2. Fill in the mandatory details:
  - Company -> Will be autofilled from Session Defaults
  - Mode of Payment -> Select one associated with Mpesa Settings
  - Party Type
  - Transaction to Pay Against
  - Account Paid From
  - Account Paid To
3. Use the `Get References` button to fetch outstanding/unpaid records.
  - Use filters to fetch `outstanding entries`.
  - The entries fetched are populated in the `References` child table.
  - Set `Mobile Numbers` and `Allocated Amount` if not fetched or auto-set.
  - Optional: Set or edit **Paid Amount** to allow auto-allocation of allocated_amounts.
4. Submit the document once you feel everything is okay.
  - This initiates a **Daraja B2C API call** for each reference.
  - Displays **real-time notification messages** showing (Success, Failure) status for each reference.
5. Automatic Status Updates:
  The main document's `status` updates based on `payment_status` on reference outcomes:
    - ✅ Paid: All references paid
    - ⚠️ Party Paid: Some paid, others failed
    - ❌ Failed: All references failed
    - 🕛 Not Initiated: No payments attempts made
6. Failed Payments?
  A **Retry Failed Payments** button is displayed to attempt the payment again for failed references.

--TODO: Insert a GIF here

#### 🧾Accounting Entries
- Salary Slip → A **Journal Entry** of type **Bank Entry** is created.
- For all others (PI/PO/Employee Advance/Expense Claim) → A **Payment Entry** is created per reference.

#### Use Cases
- Employee salary disbursements
- Supplier and vendor payments
- Expense reimbursements
- Loan disbursements


### 4. 🔍 Reconcile Payments

The **Mpesa Payment Reconciliation** tool simplifies matching incoming Mpesa payments with outstanding invoices.

**🔧 How It Works:**
1. Navigate to **Mpesa Payment Reconciliation** in the Mpesa Workspace or using Awesome Search.
2. Select the **Customer** and **Company** to filter relevant transactions.
3. Click the `Get Unreconciled Entries` and the tool displays:
  - A list of **Draft** Mpesa Payments from the Mpesa C2B Payment Register.
  - A list of **Unpaid/Outstanding** Invoices for the selected customer.
4. Optional **Filters** can be set in the Filters Section
5. **Allocate** the invoices against the draft Mpesa Payments

--TODO: Insert screenshot here

### 5. ❓Query Transaction Status

This feature allows you to check the status of an Mpesa transaction using its **Transaction ID**.

**🔧 How It Works:**
1. Open the **Mpesa C2B Payment Register** from the Mpesa Workspace.
2. Use the **Check Transaction Status** button at the top of the page.
3. Select the **Mpesa Settings** this will contain the Business Shortcode to be used
4. Enter the **Transaction ID** provided by the Customer.
5. Optional **Remarks can also be included.
6. Submit and wait for the response.
7. The system will:
  - If the transaction is successful and no record exists, create a new entry in the **Mpesa C2B Payment Regiter**
  - If the transaction is successful and record already exists, display the current status and inform you of the existing record.
  - If the transaction failed, it will notify you accordingly.

--TODO: Insert a GIF here too.

#### Use Cases:
- Verify delayed or failed transactions.
- Add missing transactions to the system for reconciliation.

---

## Key DocTypes

<h4>Mpesa Settings</h4>

This DocType is central to configuring Safaricom's Daraja API credentials, allowing for seamless integration of various Mpesa payment services (Mpesa Express, C2B, and B2C). This DocType holds the necessary credentials and identifiers for authentication and payment initiation.

1. **API Type:**  Select the type of Mpesa API integration you’re setting up (Mpesa Express, C2B, or B2C).
2. **Consumer Key:** A unique key provided by Safaricom to authenticate API calls.
3. **Consumer Secret:** A secret code paired with the Consumer Key to secure API access.
4. **Security Credential:** Encryption credential used for additional security, particularly in B2C transactions.
5. **Till Number:** Identifier for C2B payments, where customers make payments directly to a till.
6. **Business Shortcode:** A unique code used to identify your business account in the Mpesa system.
7. **Online PassKey:** An additional authentication key, specifically for initiating Mpesa Express (STK Push) transactions.
8. **Initiator Name:** API Operator configured from the Mpesa Org Portal
9. **Initiator Password:** Password paired with the Initiator Name will be encrypted to SecurityCredential for transactions.

![Screenshot from 2024-10-30 15-55-09](https://github.com/user-attachments/assets/f786501f-5c5d-4c27-9a62-ba3d76ce9562)


<h4>Mpesa C2B Payment Register URL</h4>

This DocType registers the callback URLs for incoming C2B payments. Once registered, Safaricom will notify your app when payments are received, enabling real-time reconciliation.

1. **Mpesa Settings:** Links to the configured Mpesa Settings, pulling in the necessary credentials.
2. **Company:** Specifies the company associated with the payment registration.
3. **Mode of Payment:** Identifies the payment mode for better categorization in your accounting or ERP system.
4. **Register Status:** Displays the status of the URL registration (e.g., Success, Pending), useful for troubleshooting or verification.

![Screenshot from 2024-10-30 15-56-11](https://github.com/user-attachments/assets/a30279f5-0fd7-4543-8a0a-1b8a8e2ec363)

<h4>Mpesa C2B Payment Register</h4>

This DocType records individual incoming payments via the C2B method, capturing essential details from Safaricom’s Daraja API. This data can be used for transaction verification, customer inquiries, and reconciliation with unpaid invoices.

1. **Full Name:** Customer’s full name as recorded in the Mpesa transaction.
2. **Transaction Type:** Type of transaction (typically "Pay Bill" or "Buy Goods").
3. **Trans ID:** Unique transaction ID generated by Mpesa.
4. **Trans Time:** Timestamp of the transaction.
5. **Trans Amount:** Amount transferred by the customer.
6. **Business Short Code:** The business shortcode involved in the transaction.
7. **Bill Ref Number:** Reference number associated with the transaction.
8. **Invoice Number:** Associated invoice for easy reconciliation.
9. **Org Account Balance:** Account balance at the time of the transaction.
10. **Third Party Trans ID:** Identifier from any third-party integration.
11. **Posting Date & Time:** Date and time when the transaction was recorded in your system.
12. **Company:** The company receiving the payment.
13. **Default Currency:** The currency in which the transaction was processed.
14. **Customer:** Links to the customer making the payment.
15. **Mode of Payment:** Type of payment method used.
16. **Currency:** The currency in which the transaction was processed.

![Screenshot from 2024-10-30 16-02-55](https://github.com/user-attachments/assets/5eb459ae-ccfb-4a47-bcae-e6c43b397594)

<h4>Mpesa Public Key Certificate</h4>

This DocType is used to store the required public key certificates for both sandbox and production environments. These certificates are necessary to establish secure connections between your system and Mpesa’s API, especially for encrypting sensitive information in B2C transactions.

1. **Sandbox Certificate:** Used for testing in the Daraja sandbox environment.
2. **Production Certificate:**  Used for live transactions in the production environment.

![Screenshot from 2024-10-30 16-05-19](https://github.com/user-attachments/assets/ab93b070-75df-4e76-81e5-2179cfefcffd)

<h4>Payment Gateway</h4>

The Payment Gateway DocType facilitates the integration of Mpesa with your ERPNext system’s payment gateways, enabling transactions to be routed correctly.

1. **Gateway Settings:** Contains necessary settings for the payment gateway to work with Mpesa.
2. **Gateway Controller:** Manages the routing and processing of payments through the specified payment gateway.

![Screenshot from 2024-10-30 16-06-27](https://github.com/user-attachments/assets/03d795f3-1b44-4011-8c9f-330ea747a09c)

<h4>Mpesa Payment Reconciliation</h4>

This DocType lists and organizes draft Mpesa payments, making it possible to reconcile these draft(s) mpesa payments with pending/unpaid invoices. This DocType streamlines the reconciliation process by matching Mpesa transactions with unpaid sales invoices.

1. **Customer:** Links to the customer who has any outstanding invoices.
2. **Company:** The company to which the payment(s) and invoice(s) applies.
3. **Currency:** The currency in which the transaction occured.
4. **Invoices:** Displays a list of associated unpaid invoices.
5. **Mpesa Payments:** Displays a list of draft Mpesa payments.

![Screenshot from 2024-10-30 16-07-48](https://github.com/user-attachments/assets/1a61bdce-529e-411f-9a70-1d6a6170ca4e)

## 🔐 Security
- **Credentials:** Stored securely in the `Mpesa Settings` Doctype with password fields securely encrypted.
- **Token Management:** Tokens are generated and stored in the `Mpesa Settings` and reused for requests till they expire and new ones are requested.
- **Webhooks:** Ensure your site uses HTTPS.

## 🛠️ Troubleshooting

| Problem                             | Solution                                                                          |
| ----------------------------------- | --------------------------------------------------------------------------------- |
| Invalid Access Token                | Check your Consumer Key/Secret and regenerate token                               |
| No C2B callbacks                    | Ensure your site is publicly accessible and URLs are registered                   |
| Initiator Information Invalid       | Confirm your initiator password or security credential                            |

