with source as (
    select * from {{ source('raw_olist', 'sellers') }}
),

cleaned as (
    select
        seller_id,
        upper(trim(seller_state)) as seller_state
    from source
    where seller_id is not null
)

select * from cleaned
