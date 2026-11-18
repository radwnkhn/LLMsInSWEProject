-- Optional analysis interval on the original video. Existing uploads use the full clip.
alter table public.uploads
    add column trim_start double precision,
    add column trim_end double precision,
    add constraint uploads_trim_bounds check (
        (trim_start is null and trim_end is null) or
        (trim_start is not null and trim_end is not null
         and trim_start >= 0 and trim_start < trim_end and trim_end < 'Infinity'::double precision)
    );
