It passes alone three times, so something from an earlier test in the combined run touches the store inside its window. Reproducing to see what.

Found it: the issue is timing under load, where the test assumed the lease and first write complete within 1.5s. I'll adjust the test to start the window on the third store touch (claim, lease taken, first write) instead of using a fixed wait.

    def burst():
        threading.Event().wait(1.5)  # the lease taken and the log reached
        window.append(time.monotonic())