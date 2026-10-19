  const whole = some ? WHOLE_READS : ++WHOLE_READS;
  const {found, claimed} = some ? await readTickets(only) : await readDispatch();
  if (S.project !== project || S.base !== metaform) return;  // the answer for a project the person has left
  // reads land in any order: a read of every agent begun after this one is the newer, and draws instead
  if (whole !== WHOLE_READS) return;