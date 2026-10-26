# AD vs. PDQ Inventory Reconciler

A standalone Python utility designed to automatically pair and compare Active Directory (AD) computer exports with PDQ Inventory exports. It identifies computer accounts present in AD that are missing from PDQ Inventory across multiple sites/schools.

## Key Features

- **Automated File Discovery:** Automatically scans the working directory for matching site pair CSV files (e.g., `XXXX-ITV_ad.csv` and `XXXX-ITV_pdq.csv`).
- **Hostname Normalization:** Strips trailing DNS/FQDN domain suffixes, handles case-insensitivity, and trims white space for accurate comparisons.
- **Zero External Dependencies:** Built entirely using the Python standard library (`csv`, `pathlib`, `dataclasses`).
- **Detailed Reporting:** Outputs both a human-readable text report with summary statistics and a clean CSV list of missing hosts.
