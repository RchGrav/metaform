  if (on && !EYE.view && !EYE.saved) EYE.saved = {at: camera.position.clone(), turn: camera.quaternion.clone(), fov: camera.fov};
  // still easing back to the person's view, the place it eases to is the one kept
  ... if (EYE.agentMode && figure) eyesOf(figure.mesh, true);
  else if (EYE.agent) eyesOf(null, false);