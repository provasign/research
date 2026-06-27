# Source this before any java/mvn command. JDK 26 via Homebrew (unlinked).
export JAVA_HOME="/opt/homebrew/opt/openjdk/libexec/openjdk.jdk/Contents/Home"
[ -d "$JAVA_HOME" ] || export JAVA_HOME="$(/opt/homebrew/opt/openjdk/bin/java -XshowSettings:properties -version 2>&1 | awk -F'= ' '/java.home/{print $2; exit}')"
export PATH="$JAVA_HOME/bin:$PATH"
