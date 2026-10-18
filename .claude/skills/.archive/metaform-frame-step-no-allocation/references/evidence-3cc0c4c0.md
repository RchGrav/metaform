  for (const axis of ['x', 'y', 'z']) {
    [go.at[axis], go.speed[axis]] = spring(go.at[axis], go.speed[axis], figureAt[axis], passed);
  }

From the system agent: while you are back in followIn3d on top of #bf's lines, also make the follow step's axis loop allocation-free: `for (const axis of ['x', 'y', 'z']) { [go.at[axis], go.speed[axis]] = spring(...) }` (eyes.js ~708) builds arrays every followed frame.