{"text":"code.interface.graphical#1d4 A ticket named in chat is a link that opens it, on whichever board it is"}

Memory observation recorded on code.interface.graphical: "Item numbers are hex, so `#55` is 0x55." "Lookup URLs must percent-encode `#` as %23 or the query is cut at the fragment." "/api/ticket-detail returns board and column explicitly because plain(work) does not carry column."

Restart: {"state":"restarted","address":"http://127.0.0.1:7433/","pages":"An open page reconnects on its own through its live stream, and offers a reload if the code changed."}