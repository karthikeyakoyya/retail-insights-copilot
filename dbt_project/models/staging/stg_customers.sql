with source as (
    select * from {{ source('raw_olist', 'customers') }}
),

cleaned as (
    select
        customer_id,
        upper(trim(customer_state)) as customer_state,
        trim(customer_city) as customer_city
    from source
    where customer_id is not null
)

select * from cleaned
