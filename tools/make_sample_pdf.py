"""
make_sample_pdf.py
==================

Creates `sample_data/sample_rfp.pdf`, a small four-page RFP you can upload to
try the application end to end.

Run from the project root:

    python tools/make_sample_pdf.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.simple_pdf import make_pdf  # noqa: E402

PAGE_1 = """RETAIL BANKING DIGITAL CHANNEL - REQUEST FOR PROPOSAL

1. INTRODUCTION
This Request for Proposal is issued by Meridian Bank for the supply of a digital
banking channel. Meridian Bank serves 4.2 million retail customers across 11
states and has operated since 1974. Bidders should read all sections carefully.

2. CUSTOMER MANAGEMENT
2.1 Authentication
The customer shall login using the registered mobile number.
The system shall support two-factor authentication for all customer logins.

2.2 Account Information
The system shall allow customers to view their account balance.
Customers shall be able to download their account statement in PDF format.
"""

PAGE_2 = """3. TRANSACTIONS
3.1 Fund Transfer
To reduce fraudulent transactions, the system shall require additional
verification for high-value transfers.
The system shall allow customers to schedule future-dated transfers.

3.2 Notifications
Customers shall receive an email notification for transactions above
1 lakh rupees.
The system shall send an SMS notification after a successful transaction.

Note: Meridian Bank's existing notification platform is provided by a third
party under a contract that expires in 2027.
"""

PAGE_3 = """4. REPORTING
4.1 Operational Reports
The system shall allow administrators to generate monthly transaction reports.
Reports shall be exportable in Excel format.
The system shall retain transaction reports for a minimum period of seven years.

5. SERVICE LEVELS
The solution shall be available 99.5% of the time measured monthly.
The bidder shall provide support between 08:00 and 20:00 on working days.
"""

PAGE_4 = """6. COMMERCIAL TERMS
Bids must be submitted before 17:00 on 30 November. Late bids will be rejected.
Prices shall be quoted in Indian Rupees and shall remain valid for 120 days.

7. SECURITY
The system shall restrict administrative functions to authorised users.
All customer data shall be encrypted in transit and at rest.

8. EVALUATION
Proposals will be evaluated on technical merit and commercial competitiveness.
"""


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder = os.path.join(root, "sample_data")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "sample_rfp.pdf")

    with open(path, "wb") as handle:
        handle.write(make_pdf([PAGE_1, PAGE_2, PAGE_3, PAGE_4]))

    print(f"Sample RFP written to: {path}")


if __name__ == "__main__":
    main()
