create table standup_reports (
  id uuid default gen_random_uuid() primary key,
  user_id text not null,
  date date not null default current_date,
  raw_text text not null,
  thread_ts text not null,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);
