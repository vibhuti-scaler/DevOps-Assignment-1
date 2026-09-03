# Build stage: compile the source with a full JDK.
FROM eclipse-temurin:21-jdk-alpine AS builder
WORKDIR /build
COPY src/Main.java ./
RUN javac -d classes Main.java

# Runtime stage: ship only the compiled classes on a JRE.
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=builder /build/classes ./

EXPOSE 8080
CMD ["java", "Main"]
