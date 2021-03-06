% Generated by roxygen2: do not edit by hand
% Please edit documentation in R/shiny.R
\name{shiny_plot}
\alias{shiny_plot}
\title{plot results for DSC}
\usage{
shiny_plot(res, simulate_col = "simulate", analyze_col = "analyze",
  score_col = "score", scales = "free")
}
\arguments{
\item{res}{a dataframe containing results (eg from )}

\item{simulate_col}{The name of the column that distinguishes
simulate modules.}

\item{analyze_col}{The name of the column that distinguishes
analyze modules.}

\item{score_col}{The name of the column that distinguishes score
modules.}

\item{scales}{parameter to be passed to ggplot2::facet_wrap affects
y axis scaling.}
}
\value{
A shiny plot.
}
\description{
interactive plot for results of DSC. Particularly
tailored for the simple "simulate-analyze-score" framework. It
plots boxplots of a score for each analyze module, facetting by the
simulate module.
}
