# public.submission

## Columns

| Name             | Type                     | Default | Nullable | Children                                                                                                                                              | Parents                                       | Comment |
| ---------------- | ------------------------ | ------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- | ------- |
| broker_ref       | varchar(64)              |         | true     |                                                                                                                                                       |                                               |         |
| counterparty_id  | varchar(36)              |         | false    |                                                                                                                                                       | [public.counterparty](public.counterparty.md) |         |
| country          | varchar(2)               |         | false    |                                                                                                                                                       |                                               |         |
| created_at       | timestamp with time zone |         | false    |                                                                                                                                                       |                                               |         |
| id               | varchar(36)              |         | false    | [public.audit_entry](public.audit_entry.md) [public.binding](public.binding.md) [public.decision](public.decision.md) [public.quote](public.quote.md) |                                               |         |
| line_of_business | varchar(64)              |         | false    |                                                                                                                                                       |                                               |         |
| occupancy        | varchar(64)              |         | false    |                                                                                                                                                       |                                               |         |
| postcode         | varchar(16)              |         | false    |                                                                                                                                                       |                                               |         |
| requested_cover  | varchar(255)             |         | false    |                                                                                                                                                       |                                               |         |
| tiv_eur          | bigint                   |         | false    |                                                                                                                                                       |                                               |         |

## Constraints

| Name                            | Type        | Definition                                                |
| ------------------------------- | ----------- | --------------------------------------------------------- |
| submission_counterparty_id_fkey | FOREIGN KEY | FOREIGN KEY (counterparty_id) REFERENCES counterparty(id) |
| submission_pkey                 | PRIMARY KEY | PRIMARY KEY (id)                                          |

## Indexes

| Name            | Definition                                                                |
| --------------- | ------------------------------------------------------------------------- |
| submission_pkey | CREATE UNIQUE INDEX submission_pkey ON public.submission USING btree (id) |

## Relations

```mermaid
erDiagram

"public.submission" }o--|| "public.counterparty" : "FOREIGN KEY (counterparty_id) REFERENCES counterparty(id)"
"public.audit_entry" }o--|| "public.submission" : "FOREIGN KEY (submission_id) REFERENCES submission(id)"
"public.binding" }o--|| "public.submission" : "FOREIGN KEY (submission_id) REFERENCES submission(id)"
"public.decision" }o--|| "public.submission" : "FOREIGN KEY (submission_id) REFERENCES submission(id)"
"public.quote" }o--|| "public.submission" : "FOREIGN KEY (submission_id) REFERENCES submission(id)"

"public.submission" {
  varchar_64_ broker_ref
  varchar_36_ counterparty_id FK
  varchar_2_ country
  timestamp_with_time_zone created_at
  varchar_36_ id
  varchar_64_ line_of_business
  varchar_64_ occupancy
  varchar_16_ postcode
  varchar_255_ requested_cover
  bigint tiv_eur
}
"public.counterparty" {
  varchar_2_ country
  timestamp_with_time_zone created_at
  varchar_36_ id
  varchar_255_ name
}
"public.audit_entry" {
  varchar_64_ action
  varchar_128_ actor
  timestamp_with_time_zone at
  json detail
  varchar_36_ id
  varchar_16_ outcome
  integer ruleset_version
  varchar_36_ submission_id FK
}
"public.binding" {
  timestamp_with_time_zone bound_at
  varchar_128_ bound_by
  boolean event_published
  varchar_36_ id
  varchar_64_ pas_policy_id
  varchar_64_ policy_number
  varchar_36_ quote_id FK
  varchar_16_ status
  varchar_36_ submission_id FK
}
"public.decision" {
  integer appetite_version
  timestamp_with_time_zone decided_at
  varchar_128_ decided_by
  varchar_36_ id
  varchar_16_ outcome
  json reason_codes
  varchar_36_ submission_id FK
}
"public.quote" {
  json breakdown
  timestamp_with_time_zone created_at
  varchar_128_ created_by
  varchar_3_ currency
  varchar_36_ id
  bigint premium_minor
  integer rate_table_version
  varchar_36_ submission_id FK
}
```

---

> Generated by [tbls](https://github.com/k1LoW/tbls)
