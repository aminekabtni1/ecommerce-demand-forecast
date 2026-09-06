{{ config(materialized='view') }}

with daily as (
    select * from {{ ref('int_daily_sales') }}
),

agg as (
    select
        product_id,
        any_value(product_name) as product_name,
        any_value(category) as category,
        avg(price) as avg_price,
        sum(quantity) as total_quantity,
        sum(revenue) as total_revenue,
        avg(quantity) as avg_daily_qty,
        min(sale_date) as first_sale_date,
        max(sale_date) as last_sale_date,
        count(*) as days_with_sales
    from daily
    group by product_id
)

select * from agg
