{{ config(materialized='table') }}

with daily as (
    select * from {{ ref('mart_daily_sales') }}
),

overall as (
    select
        count(distinct date) as total_days,
        sum(quantity) as total_quantity,
        sum(revenue) as total_revenue,
        avg(revenue) as avg_daily_revenue,
        avg(quantity) as avg_daily_quantity
    from daily
),

by_category as (
    select
        category,
        sum(quantity) as cat_quantity,
        sum(revenue) as cat_revenue
    from daily
    group by category
    order by cat_revenue desc
)

select
    (select total_days from overall) as total_days,
    (select total_quantity from overall) as total_quantity,
    (select total_revenue from overall) as total_revenue,
    (select avg_daily_revenue from overall) as avg_daily_revenue,
    (select category from by_category limit 1) as top_category_by_revenue,
    (select cat_revenue from by_category limit 1) as top_category_revenue
