def execute():
    from airwallex_erpnext.install import create_fields, create_roles, create_workspace
    create_roles()
    create_fields()
    create_workspace()
