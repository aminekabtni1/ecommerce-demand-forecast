{{ config(materialized='table') }}

with daily as (
    select * from {{ ref('mart_daily_sales') }}
)

select
    date,
    category,
    sum(quantity) as total_quantity,
    sum(revenue) as total_revenue,
    count(distinct product_id) as active_products,
    avg(price) as avg_price
from daily
group by date, category
order by date, category
