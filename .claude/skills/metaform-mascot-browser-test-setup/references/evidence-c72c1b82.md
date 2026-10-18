page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
page.evaluate(f'window.metaform.embody("{system.id}", "seahorse")')  # the person gives it its body
page.wait_for_function('() => window.metaform.mascot().shown', timeout=15000)