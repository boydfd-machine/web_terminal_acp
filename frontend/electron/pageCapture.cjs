function normalizePageCaptureRect(selection) {
  if (selection === null || typeof selection !== "object") {
    return null;
  }
  const left = finiteNumber(selection.left);
  const top = finiteNumber(selection.top);
  const width = finiteNumber(selection.width);
  const height = finiteNumber(selection.height);
  if (left === null || top === null || width === null || height === null) {
    return null;
  }
  const normalizedLeft = Math.max(0, Math.round(left));
  const normalizedTop = Math.max(0, Math.round(top));
  return {
    x: normalizedLeft,
    y: normalizedTop,
    width: Math.max(1, Math.round(width)),
    height: Math.max(1, Math.round(height)),
    left: normalizedLeft,
    top: normalizedTop,
  };
}

function finiteNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

module.exports = {
  normalizePageCaptureRect,
};
