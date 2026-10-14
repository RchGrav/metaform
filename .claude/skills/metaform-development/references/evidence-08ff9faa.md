const picked = event.currentTarget;  // read before the await, after which the event has no currentTarget
// the theme decides the look; web_graphics is written only when the person changes the look, never on a read
open: (payload, node, {tell}) => openFor(payload, tell),
Edit: views/settings.js followView: ULTRA.setting(document.documentElement.dataset.theme === 'space' ? 'ultra' : 'clean');