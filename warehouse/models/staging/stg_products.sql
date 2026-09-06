{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'products') }}
),

cleaned as (
    select
        cast(product_id as integer) as product_id,
        trim(title) as product_name,
        cast(price as double) as price,
        replace(trim(category), '''', '') as category,
        description,
        image as image_url,
        cast(rating_rate as double) as rating_rate,
        cast(rating_count as integer) as rating_count
    from source
    where product_id is not null
)

select * from cleaned
