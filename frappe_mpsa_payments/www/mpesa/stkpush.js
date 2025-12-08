let checking = false;
let interval = null;

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
	o.querySelector(".mp-overlay-text").innerText = text;
	o.style.display = "flex";
}

function hideOverlay() {
	document.getElementById("overlay").style.display = "none";
}

frappe.ready(async () => {
	const param = new URLSearchParams(window.location.search);

	const defaults = await frappe.call({
		method: "frappe_mpsa_payments.frappe_mpsa_payments.doctype.mpesa_express_request.mpesa_express_request.get_stkpush_defaults",
	});

	const gateways = defaults.message?.gateways || [];
	const referenceMap = defaults.message?.reference_map || {};

	const fields = ["phone_number", "payment_gateway", "reference_type", "reference_id", "amount"];
	fields.forEach((f) => {
		const val = param.get(f);
		const el = document.getElementById(f);
		if (val && el) el.value = val;
	});

	populateGateways(gateways, param.get("payment_gateway"));

	const gw = param.get("payment_gateway") || document.getElementById("payment_gateway")?.value;
	populateReferences(gw, referenceMap, param.get("reference_type"));

	registerListeners(referenceMap);

	const id = getRequestId();
	if (id) {
		showOverlay("Checking payment status...");
		beginChecking();
	}
});

function populateGateways(list, selected) {
	const el = document.getElementById("payment_gateway");
	if (!el || el.options.length) return;
	el.innerHTML = `<option value="">Select Gateway</option>`;
	list.forEach((g) => {
		const o = document.createElement("option");
		o.value = g.name;
		o.textContent = g.name;
		if (g.name === selected) o.selected = true;
		el.appendChild(o);
	});
}

function populateReferences(gw, map, selected) {
	const el = document.getElementById("reference_type");
	const grp = document.getElementById("reference-group");
	if (!el || !grp) return;

	if (!gw) {
		grp.style.display = "none";
		return;
	}

	grp.style.display = "block";
	el.innerHTML = `<option value="">Select Reference</option>`;
	(map[gw] || []).forEach((t) => {
		const o = document.createElement("option");
		o.value = t;
		o.textContent = t;
		if (t === selected) o.selected = true;
		el.appendChild(o);
	});
}

function registerListeners(map) {
	document.getElementById("payment_gateway")?.addEventListener("change", (e) => {
		populateReferences(e.target.value, map);
		updateURL();
	});

	["reference_type", "phone_number", "reference_id", "amount"].forEach((id) => {
		const el = document.getElementById(id);
		el?.addEventListener("change", updateURL);
		el?.addEventListener("input", updateURL);
	});
}

function updateURL() {
	const p = new URLSearchParams(window.location.search);
	["phone_number", "payment_gateway", "reference_type", "reference_id", "amount"].forEach(
		(f) => {
			const el = document.getElementById(f);
			if (el?.value) p.set(f, el.value);
			else p.delete(f);
		}
	);
	history.replaceState({}, "", location.pathname + "?" + p.toString());
}

async function submit_new_request() {
	const btn = document.getElementById("create-btn");

	const data = {
		phone_number: phone_number.value,
		payment_gateway: payment_gateway.value,
		reference_type: reference_type.value,
		reference_id: reference_id.value,
		amount: amount.value,
	};

	for (const k in data) if (!data[k]) return frappe.msgprint("All fields required");

	showOverlay("Sending STK Push...");

	btn.style.pointerEvents = "none";
	btn.innerText = "Processing...";

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
}

function beginChecking() {
	if (checking) return;
	checking = true;
	showOverlay("Checking payment status...");
	checkStatus();
	interval = setInterval(checkStatus, 5000);
}

function cancel_check() {
	checking = false;
	clearInterval(interval);
	hideOverlay();
}

function manual_check() {
	beginChecking();
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
		checking = false;
		clearInterval(interval);
		const redirect_to = getRequestRedirect();
		if (redirect_to) {
			window.location.href = redirect_to;
		}
	}

	if (status === "Failed") {
		checking = false;
		clearInterval(interval);
		hideOverlay();
		document.getElementById("retry-btn").style.display = "block";
	}
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
