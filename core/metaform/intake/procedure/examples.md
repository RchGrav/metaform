Examples of ifd.

- ifd1
  - scenario: Receiving Element (RE) has operative purpose (OP) to encounter -> function (EF) of Providing Element (PE)
  - requirement: {ifd} data completing a goal
  - ifd: receives
  - reasoning: RE's goal is not to send parameters, they are not the information that satisfied RE's OP.
- ifd2
  - scenario: Continued from ifd1, the PE which provided information is now an (RE) and has an (OP) to log the request with the logger (PE)
  - requirement: {ifd} logs completing its goal
  - ifd: sends
  - reasoning: sending log data satisfied the OP of the RE.
- ifd3
  - scenario: Email Client (RE) calls Email Server (PE) using SMTP and IMAP
  - requirement: direction of substantial flow
  - ifd: both
  - reasoning: RE as an email client has a goal of sends and receives email, sending or receiving only cannot satisfy RE's OP.
