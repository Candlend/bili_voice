import React from "react";

type Props = {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
};

export default function Toggle({ label, checked, onChange }: Props) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  );
}
