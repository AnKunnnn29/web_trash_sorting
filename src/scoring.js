export function scoreSelection(score, item, selectedCategory) {
  const current = {
    correct: Number(score?.correct) || 0,
    total: Number(score?.total) || 0
  };
  const isCorrect = Boolean(item && item.category === selectedCategory);

  return {
    correct: current.correct + (isCorrect ? 1 : 0),
    total: current.total + 1,
    isCorrect
  };
}
