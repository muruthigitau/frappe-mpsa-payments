import frappe
from frappe.utils.user import is_website_user

__version__ = "0.0.1"


def is_frappe_version(version: str, above: bool = False, below: bool = False):
	from frappe.pulse.utils import get_frappe_version

	current_version = get_frappe_version()
	major_version = int(current_version.split(".")[0])
	target_version = int(version.split(".")[0])

	if above:
		return major_version > target_version
	if below:
		return major_version < target_version
	return major_version == target_version


def check_app_permission():
	if frappe.session.user == "Administrator":
		return True

	if is_frappe_version('15'):
		allowed_modules = frappe.config.get_modules_from_all_apps_for_user()
	elif is_frappe_version('16', above=True):
		allowed_modules = frappe.utils.modules.get_modules_from_all_apps_for_user()
		
	allowed_modules = [x["module_name"] for x in allowed_modules]
	if "" not in allowed_modules:
		return False
	
	roles = frappe.get_roles()
	if any(role in ["System Manager"] for role in roles):
		return True

	return False