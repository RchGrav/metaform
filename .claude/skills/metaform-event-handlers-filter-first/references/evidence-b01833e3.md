    def checks(self) -> None:
        """Check for a change of its own: at once, or, while a check runs, once more after it, so a burst of changes
        costs one pass more and never one each."""
        if self.checking:
            self.check_again = True
            return
        self.checking = True
        self.spawn(self.checked_all())

assert len(burst_of_own) <= 2 * len(own), f'{len(burst_of_own)} reads for 50 changes, {len(own)} for one'
AssertionError: 50 reads for 50 changes, 1 for one

Runner.changed(tables='dispatch', kinds=[...]) names a change no table holds: the state-only announcements (working/idle, intake phase, answered permission or question, interrupt, queued turn) carry kinds ['session'].