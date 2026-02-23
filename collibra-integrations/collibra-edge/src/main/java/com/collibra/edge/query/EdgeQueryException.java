package com.collibra.edge.query;

/** Thrown when the {@link EdgeQueryEngine} cannot route or execute a query. */
public class EdgeQueryException extends Exception {
    public EdgeQueryException(String message)                  { super(message); }
    public EdgeQueryException(String message, Throwable cause) { super(message, cause); }
}
