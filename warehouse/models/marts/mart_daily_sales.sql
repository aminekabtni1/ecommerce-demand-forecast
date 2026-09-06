{{ config(materialized='table') }}

with daily as (
    select * from {{ ref('int_daily_sales') }}
)

select
    sale_date as date,
    product_id,
    category,
    product_name,
    price,
    quantity,
    revenue,
    -- rolling 7d avg for dashboard sparklines
    avg(quantity) over (partition by product_id order by sale_date rows between 6 preceding and current row) as rolling_7d_avg_qty,
    avg(revenue)  over (partition by product_id order by sale_date rows between 6 preceding and current row) as rolling_7d_avg_revenue,
    -- rolling 14d for anomaly baseline
    avg(quantity) over (partition by product_id order by sale_date rows between 13 preceding and current row) as rolling_14d_avg_qty,
    stddev_pop(quantity) over (partition by product_id order by sale_date rows between 13 preceding and current row) as rolling_14d_std_qty
from daily
order by date, product_id
