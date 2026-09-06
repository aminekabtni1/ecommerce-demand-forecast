{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'daily_sales') }}
),

cleaned as (
    select
        cast(date as date) as sale_date,
        cast(product_id as integer) as product_id,
        replace(trim(category), '''', '') as category,
        trim(title) as product_name,
        cast(price as double) as price,
        cast(quantity as integer) as quantity,
        cast(revenue as double) as revenue
    from source
    where product_id is not null
      and date is not null
)

select * from cleaned
