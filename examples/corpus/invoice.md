# Example invoice workflow

An invoice record has an invoice identifier, amount, currency and due date.
Flag duplicate invoice identifiers before joining invoices to payment records.

A many-to-one join requires unique keys in the payment lookup table.
Unmatched records go to a human review queue rather than being silently discarded.
