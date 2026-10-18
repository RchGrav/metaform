# Embody setup in test_web.py

A focused browser test for the mascot's motion, with the body step first:

    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    page.evaluate(f'window.metaform.embody("{system.id}", "seahorse")')
    page.wait_for_function('() => window.metaform.mascot().shown', timeout=15000)
    page.wait_for_timeout(2500)

The nearest existing mascot body test passed with the same setup on the shared tree.
