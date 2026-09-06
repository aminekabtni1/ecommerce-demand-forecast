{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'carts') }}
),

cleaned as (
    select
        cast(cart_id as integer) as cart_id,
        cast(user_id as integer) as user_id,
        cast(cart_date as timestamp) as cart_date,
        cast(product_id as integer) as product_id,
        cast(quantity as integer) as quantity
    from source
    where product_id is not null
)

select * from cleaned
