  try { tickets = boardTickets((await read('work', {limit: 0})).results || []); }
  catch (error) { toast(error.message); return; }
  if (S.project !== project || S.base !== metaform) return;  // a later choice's read draws its own tickets
  B.tickets = tickets;