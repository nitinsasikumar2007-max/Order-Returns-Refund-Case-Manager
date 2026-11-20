# Project overview

## User roles and permissions

| Role | Main permissions |
|---|---|
| Customer Support Agent | Validate order references, create return requests, view case progress |
| Warehouse Inspector | Record inspection results and replacement tracking details |
| Finance Officer | Record manual refund amount and reference |
| Returns Manager | Create requests, make approve/reject decisions, record refunds/replacements, close resolved cases |

## Return lifecycle

`Create request → Inspection → Manager decision → Refund or replacement → Close case`

An inspection can be Pass, Fail or Needs Review. A passing inspection is required before a manager can approve a request. A manager may reject a failed inspection. A refund requires a positive amount no greater than the order value and a manual reference. Replacement dispatch requires a tracking reference.

## Data safety

The app uses fictional demo order/customer data. Refund recording is a bookkeeping/status operation only; it never contacts a bank, wallet or payment gateway.
