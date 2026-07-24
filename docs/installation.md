# Installation

## Prerequisites

Use Frappe 16 and ERPNext 16 on a supported Python 3.12+ runtime. Complete a database backup before installing or upgrading. The site must have working workers, scheduler, Redis queues, and outbound HTTPS access to the selected Airwallex API environment.

## Install from a release

```bash
cd /home/frappe/frappe-bench
bench get-app https://github.com/lutzkind/frappe-airwallex.git --branch v1.0.4
bench --site your-site.example install-app airwallex_erpnext
bench --site your-site.example migrate
bench build --app airwallex_erpnext
bench restart
```

For container images, pin both the tag and its resolved commit in the image build metadata. Do not build production from an unpinned branch.

## Upgrade

```bash
cd apps/airwallex_erpnext
git fetch --tags
git checkout v1.0.4
cd ../..
bench --site your-site.example migrate
bench build --app airwallex_erpnext
bench restart
```

Run the migration report before and after upgrading. Confirm that custom Airwallex identifiers, mappings, and private File attachments remain present.

## Initial validation

1. Confirm `bench version` reports `airwallex_erpnext 1.0.4`.
2. Open **Airwallex Settings** and create a disabled connection.
3. Map its ERPNext company and default currency.
4. Add one Airwallex Account Mapping per enabled wallet currency.
5. Enter the Client ID and API key in the Frappe Password fields.
6. Test the connection and discover capabilities.
7. Run an existing-data migration dry run.
8. Run a module-limited synchronization dry run.
9. Enable the connection only after the result has been reviewed.

Never enable accounting-document creation as part of the installation itself.
