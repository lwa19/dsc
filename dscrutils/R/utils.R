merge_lists <- function(x, y, ...) {
  if (length(x) == 0)
    return(y)
  if (length(y) == 0)
    return(x)
  for (i in 1:length(names(y)))
    x[names(y)[i]] <- y[i]
  return(x)
}

# This function is currently only used by the dsc Python module.
load_inputs <- function (files, loader) {
  if (length(files) == 1)
      return(loader(files[1]))
  out <- list()
  for (i in 1:length(files))
    out <- merge_lists(out,loader(files[i]))
  return(out)
}

thisFile <- function() {
  cmdArgs <- commandArgs(trailingOnly = FALSE)
  needle  <- "--file="
  match   <- grep(needle,cmdArgs)
  if (length(match) > 0) {
    ## Rscript
    path <- cmdArgs[match]
    path <- gsub("\\~\\+\\~", " ", path)
    return(normalizePath(sub(needle, "", path)))
  } else {
    ## 'source'd via R console
    return(sys.frames()[[1]]$ofile)
  }
}

load_script <- function() {
  fileName <- thisFile()
  return(ifelse(!is.null(fileName) && file.exists(fileName),
                readChar(fileName,file.info(fileName)$size),""))
}

# This function is currently only used in the dsc Python module.
#
#' @importFrom utils capture.output
#' @importFrom utils sessionInfo
save_session <- function (start_time, id) {
  time    <- as.list(proc.time() - start_time)
  script  <- load_script()
  session <- capture.output(print(sessionInfo()))
  return(list(time = time,script = script,replicate = id,session = session))
}

#' @export
run_cmd <- function(cmd_str, shell_exec="/bin/bash", fout='', ferr='', quit_on_error=TRUE, ...) {
  if (ferr!=FALSE) {
    write("Running shell command:", stderr())
    write(cmd_str, stderr())
  }
  out <- system2(shell_exec, args = c("-c", shQuote(cmd_str)), stdout = fout, stderr=ferr, ...)
  if (out != 0 && quit_on_error && fout != TRUE && ferr != TRUE)
    stop(paste(strsplit(cmd_str, " +")[[1]][1], "command failed (returned a non-zero exit status)"))
  return(out)
}

#' @importFrom digest digest
#' @export
str_to_int = function(x) {
  h = digest(x,algo='xxhash32')
  xx = strsplit(tolower(h), "")[[1L]]
  pos = match(xx, c(0L:9L, letters[1L:6L]))
  sum((pos - 1L) * 16^(rev(seq_along(xx) - 1)))
}

# Finds all .R and .r files within a folder and sources them.
source_dir <- function (folder, recursive = TRUE, ...) {
  files <- list.files(folder, pattern = "[.][rR]$",full.names = TRUE,
                      recursive = recursive)
  if (length(files))
    src <- invisible(lapply(files, source, ...))
}

# This function is currently only used by the dsc Python module.
source_dirs <- function(folders, ...)
  for (folder in folders)
    source_dir(folder,...)

# This function is currently only used by the dsc Python module.
#
#' @importFrom tools file_ext
#' @importFrom yaml yaml.load_file
read_dsc <- function (infile) {
  inext = file_ext(infile)
  if (inext == "") {
    for (item in c("rds", "pkl", "yml")) {
      if (file.exists(paste0(infile, ".", item))) {
        inext = item
        infile = paste0(infile, ".", item)
        break
      }
    }
  }
  if (inext == "")
    stop(paste("Cannot determine extension for input file", infile))
  else if (inext == 'pkl') {
    ## Do not use `importFrom` for reticulate because
    ## this is not always required
    ## and when it is required the DSC parser code
    ## will check and install the package.
    if (!requireNamespace("reticulate",quietly = TRUE))
      stop("Cannot read Python's `pkl` files due to missing `reticulate` package.")
    result = reticulate::py_load_object(infile)
    return(rapply(result, reticulate::py_to_r, classes = "python.builtin.object", how = "replace"))
  } else if (inext == 'yml')
    return(yaml.load_file(infile))
  else
    return(readRDS(infile))
}

# This implements a "null" progressbar; currently, the
# "progressbar_enabled" feature does not work for progress_bar.
#
#' @importFrom R6 R6Class
null_progress_bar <-
  R6Class("null_progress_bar",public = list(tick = function(...) {}))
