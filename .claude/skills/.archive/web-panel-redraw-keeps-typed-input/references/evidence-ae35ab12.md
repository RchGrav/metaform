user: This i fucking sucks!!!!   I cant even raise an issue about a problem because it keeps fucking refreshing and closing the danm window
assistant: Fixed. Reload the page, and Raise an issue will stay open while you write.

**What I changed:** the Object tab is now left alone while you're writing in it, meaning while the Raise an issue form is open or the cursor is in any of its fields. It used to be redrawn on every map change, and with agents writing every few seconds that kept wiping the form. Map changes that come in meanwhile show up once you're done. All four paths that redrew the tab check this now (`writingInPanel` in `core/dom.js`).
tool_result: raise button 1
5s visible=True text='probe: the panel should keep this text'
10s visible=True text='probe: the panel should keep this text'
30s visible=True text='probe: the panel should keep this text'
errors []