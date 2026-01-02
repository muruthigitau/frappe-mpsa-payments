let checking = false;
let interval = null;
window.current_converted_amount = "{{ mpesa_request.amount or '0.00' }}";

function getRequestRedirect() {
	const p = new URLSearchParams(window.location.search);
	return p.get("redirect_to");
}

function getRequestId() {
	const p = new URLSearchParams(window.location.search);
	return p.get("id");
}

function showOverlay(text = "Processing...") {
	const o = document.getElementById("overlay");
	if (o) {
		o.querySelector(".mp-overlay-text").innerText = text;
		o.style.display = "flex";
	}
}

function hideOverlay() {
	const o = document.getElementById("overlay");
	if (o) o.style.display = "none";
}

frappe.ready(() => {
	["phone_number", "base_amount", "reference_id"].forEach((id) => {
		const el = document.getElementById(id);
		if (el && !el.disabled) {
			el.addEventListener("input", updateURL);
		}
	});

	const id = getRequestId();
	if (id) {
		beginChecking();
	} else {
		update_total_display();
	}
});

function updateURL() {
	const p = new URLSearchParams(window.location.search);
	const fields = ["phone_number", "base_amount", "reference_id"];

	fields.forEach((field) => {
		const el = document.getElementById(field);
		if (el && el.value) p.set(field, el.value);
		else p.delete(field);
	});

	history.replaceState({}, "", location.pathname + "?" + p.toString());
}

async function update_total_display() {
	const baseAmount = document.getElementById("base_amount")?.value;
	const currencyLabel = document.getElementById("currency_label");
	const currency = currencyLabel ? currencyLabel.innerText.trim() : "KES";
	const gatewayInput = document.getElementById("payment_gateway");
	const gatewayValue = gatewayInput ? gatewayInput.value : "";
	const displayElement = document.getElementById("total_display");

	if (!baseAmount || parseFloat(baseAmount) <= 0) {
		if (displayElement) displayElement.innerText = "Ksh 0.00";
		window.current_converted_amount = "0.00";
		return;
	}

	if (currency === "KES") {
		const formatted = parseFloat(baseAmount).toFixed(2);
		if (displayElement) displayElement.innerText = `Ksh ${formatted}`;
		window.current_converted_amount = formatted;
		return;
	}

	try {
		const r = await frappe.call({
			method: "frappe_mpsa_payments.utils.utils.convert_amount_to_kes",
			args: {
				amount: baseAmount,
				currency: currency,
				settings: gatewayValue.replace("Mpesa-", ""),
			},
		});
		if (r.message && displayElement) {
			const converted = parseFloat(r.message).toFixed(2);
			displayElement.innerText = `Ksh ${converted}`;
			window.current_converted_amount = converted;
		}
	} catch (e) {
		console.error("Currency conversion failed", e);
	}
}

async function submit_new_request() {
	const btn = document.getElementById("create-btn");

	const data = {
		phone_number: document.getElementById("phone_number")?.value,
		payment_gateway: document.getElementById("payment_gateway")?.value,
		reference_type: document.getElementById("reference_type")?.value,
		reference_id: document.getElementById("reference_id")?.value,
		base_amount: document.getElementById("base_amount")?.value,
		currency: "KES",
		amount: window.current_converted_amount,
		title: document.getElementById("title")?.innerText || "",
		description: document.getElementById("description")?.innerText || "",
	};

	if (!data.phone_number || !data.base_amount || !data.reference_id) {
		return frappe.msgprint(__("Please fill in all required fields."));
	}

	showOverlay("Sending STK Push...");
	if (btn) {
		btn.style.pointerEvents = "none";
		btn.innerHTML = "<span>Processing...</span>";
	}

	try {
		const res = await frappe.call({
			method: "frappe_mpsa_payments.frappe_mpsa_payments.doctype.mpesa_express_request.mpesa_express_request.create_new_request",
			args: data,
		});
		const redirect_to = getRequestRedirect();
		location.href =
			location.pathname +
			"?id=" +
			res.message +
			(redirect_to ? "&redirect_to=" + encodeURIComponent(redirect_to) : "");
	} catch (e) {
		hideOverlay();
		if (btn) {
			btn.style.pointerEvents = "all";
			btn.innerHTML = `<span>Pay Now</span><svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14M12 5l7 7-7 7"></path></svg>`;
		}
	}
}

function beginChecking() {
	if (checking) return;
	checking = true;
	showOverlay("Checking payment status...");
	checkStatus();
	interval = setInterval(checkStatus, 5000);
}

async function checkStatus() {
	if (!checking) return;
	const id = getRequestId();
	if (!id) return;

	const r = await frappe.call({
		method: "frappe_mpsa_payments.frappe_mpsa_payments.doctype.mpesa_express_request.mpesa_express_request.get_request_status",
		args: { name: id },
	});

	const status = r.message?.status;
	if (!status) return;

	const badge = document.getElementById("status-badge");
	if (badge) badge.innerText = status;

	if (status === "Completed") {
		stopChecking();
		const redirect_to = getRequestRedirect();
		if (redirect_to) window.location.href = redirect_to;
		else hideOverlay();
	}

	if (status === "Failed") {
		stopChecking();
		hideOverlay();
		const retryBtn = document.getElementById("retry-btn");
		if (retryBtn) retryBtn.style.display = "block";
	}
}

function stopChecking() {
	checking = false;
	clearInterval(interval);
}

function cancel_check() {
	stopChecking();
	hideOverlay();
}

async function retry_stk() {
	const id = getRequestId();
	if (!id) return;
	showOverlay("Retrying payment...");
	await frappe.call({
		method: "frappe_mpsa_payments.frappe_mpsa_payments.doctype.mpesa_express_request.mpesa_express_request.retry_stkpush",
		args: { name: id },
	});
	beginChecking();
}
