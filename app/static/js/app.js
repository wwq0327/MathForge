// HTMX + KaTeX 集成：局部刷新后重新渲染公式
document.addEventListener("htmx:afterSwap", function (event) {
  if (typeof renderMathInElement === "function") {
    renderMathInElement(event.target, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$", right: "$", display: false },
      ],
    });
  }
});
