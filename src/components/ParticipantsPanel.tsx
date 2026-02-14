// ParticipantsPanel.tsx - Component for managing meeting participants

import React, { useState, useEffect } from "react";
import { User, MeetingParticipant, MeetingInvitation } from "../types";
import {
  searchUsers,
  inviteUserToMeeting,
  getMeetingParticipants,
  removeParticipant,
  getMyInvitations,
  respondToInvitation,
} from "../services/geminiService";
import { Users, UserPlus, UserMinus, Search, X, Check } from "lucide-react";

interface ParticipantsPanelProps {
  meetingId: string;
  isHost: boolean;
  onParticipantsChange?: () => void;
}

const ParticipantsPanel: React.FC<ParticipantsPanelProps> = ({
  meetingId,
  isHost,
  onParticipantsChange,
}) => {
  const [participants, setParticipants] = useState<MeetingParticipant[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<User[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showInvite, setShowInvite] = useState(false);

  useEffect(() => {
    loadParticipants();
  }, [meetingId]);

  useEffect(() => {
    if (searchQuery.length >= 2) {
      const debounce = setTimeout(() => {
        performSearch();
      }, 300);
      return () => clearTimeout(debounce);
    } else {
      setSearchResults([]);
    }
  }, [searchQuery]);

  const loadParticipants = async () => {
    try {
      setIsLoading(true);
      const data = await getMeetingParticipants(meetingId);
      setParticipants(data);
    } catch (err) {
      console.error("Failed to load participants:", err);
      setError("Failed to load participants");
    } finally {
      setIsLoading(false);
    }
  };

  const performSearch = async () => {
    try {
      setIsSearching(true);
      const results = await searchUsers(searchQuery);
      // Filter out users already in the meeting
      const participantIds = new Set(participants.map((p) => p.user_id));
      const filtered = results.filter(
        (user: User) => !participantIds.has(user.id),
      );
      setSearchResults(filtered);
    } catch (err) {
      console.error("Search failed:", err);
    } finally {
      setIsSearching(false);
    }
  };

  const handleInvite = async (username: string) => {
    try {
      setError(null);
      await inviteUserToMeeting(meetingId, username);
      setSearchQuery("");
      setSearchResults([]);
      setShowInvite(false);
      // Refresh participants
      await loadParticipants();
      onParticipantsChange?.();
    } catch (err: any) {
      setError(err.message || "Failed to invite user");
    }
  };

  const handleRemove = async (userId: string) => {
    if (!confirm("Are you sure you want to remove this participant?")) {
      return;
    }

    try {
      setError(null);
      await removeParticipant(meetingId, userId);
      await loadParticipants();
      onParticipantsChange?.();
    } catch (err: any) {
      setError(err.message || "Failed to remove participant");
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
          <Users size={20} />
          Participants ({participants.length})
        </h3>
        {isHost && (
          <button
            onClick={() => setShowInvite(!showInvite)}
            className="flex items-center gap-2 px-3 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg transition-colors text-sm"
          >
            <UserPlus size={16} />
            Invite
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-200 px-3 py-2 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Invite Section */}
      {showInvite && isHost && (
        <div className="bg-gray-700/50 rounded-lg p-3 space-y-3">
          <div className="relative">
            <Search
              className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"
              size={18}
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search users by username or email..."
              className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* Search Results */}
          {searchResults.length > 0 && (
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {searchResults.map((user) => (
                <div
                  key={user.id}
                  className="flex items-center justify-between bg-gray-800 p-2 rounded-lg hover:bg-gray-750 transition-colors"
                >
                  <div>
                    <p className="text-white font-medium">{user.username}</p>
                    {user.full_name && (
                      <p className="text-sm text-gray-400">{user.full_name}</p>
                    )}
                  </div>
                  <button
                    onClick={() => handleInvite(user.username)}
                    className="px-3 py-1 bg-cyan-600 hover:bg-cyan-700 text-white rounded text-sm transition-colors"
                  >
                    Invite
                  </button>
                </div>
              ))}
            </div>
          )}

          {isSearching && (
            <p className="text-center text-gray-400 text-sm">Searching...</p>
          )}

          {searchQuery.length >= 2 &&
            !isSearching &&
            searchResults.length === 0 && (
              <p className="text-center text-gray-400 text-sm">
                No users found
              </p>
            )}
        </div>
      )}

      {/* Participants List */}
      {isLoading ? (
        <div className="text-center text-gray-400 py-4">Loading...</div>
      ) : (
        <div className="space-y-2">
          {participants.map((participant) => (
            <div
              key={participant.id}
              className="flex items-center justify-between bg-gray-700/50 p-3 rounded-lg"
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-cyan-600 flex items-center justify-center text-white font-semibold">
                  {participant.user?.username?.charAt(0).toUpperCase() || "?"}
                </div>
                <div>
                  <p className="text-white font-medium">
                    {participant.user?.username || "Unknown"}
                    {participant.role === "host" && (
                      <span className="ml-2 text-xs bg-cyan-600 px-2 py-1 rounded-full">
                        Host
                      </span>
                    )}
                  </p>
                  {participant.user?.full_name && (
                    <p className="text-sm text-gray-400">
                      {participant.user.full_name}
                    </p>
                  )}
                </div>
              </div>

              {isHost && participant.role !== "host" && (
                <button
                  onClick={() => handleRemove(participant.user_id)}
                  className="p-2 text-gray-400 hover:text-red-500 hover:bg-gray-600 rounded-full transition-colors"
                  title="Remove participant"
                >
                  <UserMinus size={18} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ParticipantsPanel;

// ============================================================================
// INVITATIONS COMPONENT
// ============================================================================

interface InvitationsListProps {
  onInvitationResponse?: (meetingId?: string) => void;
}

export const InvitationsList: React.FC<InvitationsListProps> = ({
  onInvitationResponse,
}) => {
  const [invitations, setInvitations] = useState<MeetingInvitation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadInvitations();
  }, []);

  const loadInvitations = async () => {
    try {
      setIsLoading(true);
      const data = await getMyInvitations("pending");
      setInvitations(data);
    } catch (err) {
      console.error("Failed to load invitations:", err);
      setError("Failed to load invitations");
    } finally {
      setIsLoading(false);
    }
  };

  const handleRespond = async (
    invitationId: string,
    meetingId: string,
    status: "accepted" | "declined",
  ) => {
    try {
      setError(null);
      await respondToInvitation(invitationId, status);
      await loadInvitations();

      if (status === "accepted") {
        onInvitationResponse?.(meetingId);
      } else {
        onInvitationResponse?.();
      }
    } catch (err: any) {
      setError(err.message || "Failed to respond to invitation");
    }
  };

  if (isLoading) {
    return (
      <div className="text-center text-gray-400">Loading invitations...</div>
    );
  }

  if (invitations.length === 0) {
    return null;
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4 space-y-3">
      <h3 className="text-lg font-semibold text-white">
        Meeting Invitations ({invitations.length})
      </h3>

      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-200 px-3 py-2 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="space-y-3">
        {invitations.map((invitation) => (
          <div
            key={invitation.id}
            className="bg-gray-700/50 p-3 rounded-lg space-y-2"
          >
            <div>
              <p className="text-white font-medium">
                {invitation.meeting?.title || "Meeting"}
              </p>
              <p className="text-sm text-gray-400">
                From {invitation.inviter?.username || "Unknown"}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {new Date(invitation.created_at).toLocaleString()}
              </p>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() =>
                  handleRespond(
                    invitation.id,
                    invitation.meeting_id,
                    "accepted",
                  )
                }
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors"
              >
                <Check size={16} />
                Accept
              </button>
              <button
                onClick={() => handleRespond(invitation.id, "declined")}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
              >
                <X size={16} />
                Decline
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
