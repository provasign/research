import type { Notification } from "./models.ts";

export interface NotificationChannel {
  readonly id: string;
  send(msg: Notification): boolean;
  validate(msg: Notification): boolean;
  describe(): string;
}

export class Dispatcher {
  private channels: NotificationChannel[];

  constructor(channels: NotificationChannel[]) {
    this.channels = channels;
  }

  fanout(msg: Notification): string[] {
    const delivered: string[] = [];
    for (const channel of this.channels) {
      if (channel.send(msg)) {
        delivered.push(channel.id);
      }
    }
    return delivered;
  }

  descriptions(): string[] {
    return this.channels.map((c) => c.describe());
  }
}
