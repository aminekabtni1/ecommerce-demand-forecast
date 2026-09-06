{{ config(materialized='view') }}

-- Daily grain: ensures one row per date x product, with 0-filled missing combos if needed
-- For now we trust stg_sales has dense dates (synthetic does); in production we'd cross-join calendar.

with sales as (
    select * from {{ ref('stg_sales') }}
),

products as (
    select * from {{ ref('stg_products') }}
),

joined as (
    select
        s.sale_date,
        s.product_id,
        s.category,
        s.product_name,
        s.price,
        s.quantity,
        s.revenue,
        p.rating_rate,
        p.rating_count
    from sales s
    left join products p using (product_id)
)

select * from joined
