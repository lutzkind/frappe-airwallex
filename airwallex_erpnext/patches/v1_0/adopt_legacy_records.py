def execute():
    # Adoption is deliberately settings-specific and is run through the migration API.
    # This patch only guarantees that legacy records remain untouched during install.
    return None
