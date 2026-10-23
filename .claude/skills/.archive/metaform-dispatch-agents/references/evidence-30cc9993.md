                needed = {'state': 'needs_choice', 'work_id': work_id, 'catalog': catalog,
                      'strengths': strengths_of(ctx, catalog), 'task_types': dict(TASKS)}
            if fallback is not None:
                needed['reason'] = rejection_reason(fallback, catalog, overrides)
            return needed