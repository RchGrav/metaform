// The onboarding view (dev/user_agent_interfaces-ux.md section 12). Every word comes from strings.ts.
// On simulated data it offers the simulated intake. On a real home it shows only commands that
// exist, and when the home has no project it says so and can read the project list again.

import { useState } from "react";
import * as strings from "../strings";
import { SimulatedBadge } from "./Chrome";

export function Onboarding(props: {
  /** True on simulated data: the simulated intake and the planned command show. */
  simulated: boolean;
  /** True when the source answered with no project. */
  empty: boolean;
  onSimulateIntake: () => void;
  /** Reads the project list again and resolves to the number of projects, or null when the read failed. */
  onCheckAgain: () => Promise<number | null>;
  startCommand: string;
  onClose?: () => void;
}) {
  const o = strings.onboarding;
  const [stillEmpty, setStillEmpty] = useState(false);
  const check = () => {
    setStillEmpty(false);
    void props.onCheckAgain().then((count) => setStillEmpty(count === 0));
  };
  return (
    <section className="onboarding" aria-labelledby="onboarding-title">
      <h2 id="onboarding-title">{o.title}</h2>
      {props.empty && !props.simulated && <p className="no-project">{o.noProject}</p>}
      <ol>
        <li>
          <h3>{o.register.title}</h3>
          <p>{o.register.body}</p>
          <code>{o.register.command}</code>
          {props.simulated ? (
            <p>
              <span className="badge">{o.register.plannedLabel}</span> <code>{o.register.plannedCommand}</code>
            </p>
          ) : (
            <>
              <p>{o.register.terminalBody}</p>
              <code>{o.register.terminalCommand}</code>
              {props.empty && (
                <p>
                  <button type="button" onClick={check}>{o.checkAgain}</button>{" "}
                  <span role="status">{stillEmpty ? o.stillNoProject : ""}</span>
                </p>
              )}
            </>
          )}
        </li>
        <li>
          <h3>{o.intake.title}</h3>
          <p>{o.intake.body}</p>
          {props.simulated && (
            <>
              <button type="button" onClick={props.onSimulateIntake}>{o.intake.button}</button> <SimulatedBadge />
            </>
          )}
        </li>
        <li>
          <h3>{o.reopen.title}</h3>
          <p>{o.reopen.body}</p>
          <code>{o.reopen.command}</code>
          {props.startCommand !== o.reopen.command && <p>{o.reopen.prototypeCommand(props.startCommand)}</p>}
        </li>
      </ol>
      {props.onClose && (
        <button type="button" className="close" onClick={props.onClose} aria-label={strings.details.close}>×</button>
      )}
    </section>
  );
}
