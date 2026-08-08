create policy "deny public access to formation episodes" on public.formation_episodes
  for all to anon, authenticated using (false) with check (false);

create policy "deny public access to episode outcomes" on public.episode_outcomes
  for all to anon, authenticated using (false) with check (false);
